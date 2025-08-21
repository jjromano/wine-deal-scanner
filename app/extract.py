"""Deal extraction utilities for parsing LastBottle data."""

import re
import unicodedata
from typing import Any

from playwright.async_api import Page
from selectolax.parser import HTMLParser

from .models import Deal, DealDetails, normalize_bottle_size


def deal_key(title: str, vintage: str | None, price: float) -> str:
    """
    Generate a unique key for deal deduplication.

    Args:
        title: Wine title/name
        vintage: Wine vintage year (optional)
        price: Deal price

    Returns:
        Unique string key for the deal
    """
    # Normalize title: lowercase, remove accents, remove extra spaces, strip punctuation
    # First remove accents/diacritics
    normalized_title = unicodedata.normalize('NFD', title.lower().strip())
    normalized_title = ''.join(c for c in normalized_title if unicodedata.category(c) != 'Mn')
    # Remove punctuation and normalize spaces
    normalized_title = re.sub(r'[^\w\s]', '', normalized_title)
    normalized_title = re.sub(r'\s+', ' ', normalized_title)

    vintage_str = vintage if vintage else "unknown"
    price_str = f"{price:.2f}"

    return f"{normalized_title}|{vintage_str}|{price_str}"


def _to_float(val: Any) -> float | None:
    """Convert various value types to float."""
    if val is None:
        return None
    if isinstance(val, int | float):
        return float(val)
    if isinstance(val, str):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", val.replace(",", ""))
        return float(m.group(1)) if m else None
    return None


def pick_lastbottle_price(obj: Any) -> float | None:
    """
    Return ONLY the 'last bottle' price (the site's offer). Ignore 'retail' and 'best web'.
    Handles JSON dicts with nested or flat keys and HTML/text blobs.
    """
    # JSON/dict variants
    if isinstance(obj, dict):
        # Common nested shapes
        for k in ("prices", "pricing", "priceInfo"):
            sub = obj.get(k)
            if isinstance(sub, dict):
                for lk in ("last_bottle", "lastBottle", "lastBottlePrice", "last_bottle_price", "lb"):
                    if lk in sub:
                        v = _to_float(sub.get(lk))
                        if v is not None:
                            return v
        # Flat keys on root
        for lk in ("last_bottle", "lastBottle", "lastBottlePrice", "last_bottle_price", "lb"):
            if lk in obj:
                v = _to_float(obj.get(lk))
                if v is not None:
                    return v
    # Text/HTML fallback: look for 'last bottle' near a $value
    s = str(obj)
    m = re.search(r"last\s*bottle[^$€£]*([$€£]\s*[0-9]+(?:\.[0-9]+)?)", s, flags=re.IGNORECASE)
    if m:
        return _to_float(m.group(1))
    # No explicit 'last bottle' found: return None (we do NOT use retail/best web)
    return None


def extract_deal_from_json(obj: dict[str, Any]) -> Deal | None:
    """
    Extract a Deal from JSON/API response data.

    Args:
        obj: JSON object containing deal data

    Returns:
        Deal instance if extraction successful, None otherwise
    """
    try:
        # TODO: Update these field mappings based on actual LastBottle API structure
        # This is a placeholder implementation

        # Required fields
        title = obj.get("name") or obj.get("title") or obj.get("product_name")
        url = obj.get("url") or obj.get("link") or obj.get("product_url")

        # Use pick_lastbottle_price for precise price extraction
        price = pick_lastbottle_price(obj)
        if price is None:
            # Fallback to generic price fields if no LastBottle-specific price found
            price = obj.get("price") or obj.get("sale_price") or obj.get("current_price")
            price = _to_float(price)

        if not all([title, price, url]):
            return None

        # Optional fields
        list_price = obj.get("list_price") or obj.get("original_price") or obj.get("msrp")
        list_price = _to_float(list_price)

        vintage = obj.get("vintage") or obj.get("year")
        if vintage and not isinstance(vintage, str):
            vintage = str(vintage)

        region = obj.get("region") or obj.get("appellation") or obj.get("origin")

        # Determine bottle size from available text
        size_text = title
        size_label = obj.get("size") or obj.get("bottle_size") or obj.get("format")
        if size_label:
            size_text = f"{title} {size_label}"
        bottle_size_ml = normalize_bottle_size(size_text)

        return Deal(
            title=str(title),
            price=float(price),
            list_price=list_price,
            vintage=vintage,
            region=region,
            url=str(url),
            bottle_size_ml=bottle_size_ml
        )

    except (KeyError, ValueError, TypeError):
        # Log the error in a real implementation
        return None


async def extract_deal_from_dom(page: Page) -> Deal | None:
    """
    Extract a Deal from DOM elements using Playwright.

    Args:
        page: Playwright page instance

    Returns:
        Deal instance if extraction successful, None otherwise
    """
    try:
        # TODO: Update these selectors based on actual LastBottle DOM structure
        # These are placeholder selectors that need to be customized

        # Extract title
        title_element = await page.query_selector(
            "h1.product-title, .wine-name, .product-name, h1"
        )
        if not title_element:
            return None
        title = await title_element.text_content()
        if not title:
            return None
        title = title.strip()

        # Try to get LastBottle-specific price first
        # TODO: Update these selectors based on actual LastBottle DOM structure
        page_content = await page.content()
        price = pick_lastbottle_price(page_content)

        if price is None:
            # Fallback to general price extraction from DOM
            price_element = await page.query_selector(
                ".sale-price, .current-price, .price, .cost"
            )
            if not price_element:
                return None
            price_text = await price_element.text_content()
            if not price_text:
                return None

            # Extract numeric price
            price = _to_float(price_text)
            if price is None:
                return None

        # Extract list price (optional)
        list_price = None
        list_price_element = await page.query_selector(
            ".original-price, .list-price, .was-price, .msrp"
        )
        if list_price_element:
            list_price_text = await list_price_element.text_content()
            if list_price_text:
                list_price = _to_float(list_price_text)

        # Extract vintage (optional)
        vintage = None
        vintage_element = await page.query_selector(
            ".vintage, .year, .wine-year"
        )
        if vintage_element:
            vintage_text = await vintage_element.text_content()
            if vintage_text:
                vintage_match = re.search(r'\b(19|20)\d{2}\b', vintage_text)
                if vintage_match:
                    vintage = vintage_match.group()

        # Extract region (optional)
        region = None
        region_element = await page.query_selector(
            ".region, .appellation, .origin, .location"
        )
        if region_element:
            region_text = await region_element.text_content()
            if region_text:
                region = region_text.strip()

        # Extract bottle size from available text
        size_text = title
        size_element = await page.query_selector(
            ".bottle-size, .size, .format, .volume"
        )
        if size_element:
            size_label = await size_element.text_content()
            if size_label:
                size_text = f"{title} {size_label.strip()}"
        bottle_size_ml = normalize_bottle_size(size_text)

        # Get current URL
        url = page.url

        return Deal(
            title=title,
            price=price,
            list_price=list_price,
            vintage=vintage,
            region=region,
            url=url,
            bottle_size_ml=bottle_size_ml
        )

    except Exception:
        # Log the error in a real implementation
        return None


def _extract_vintage_from_text(text: str) -> int | None:
    """Extract vintage year from text."""
    # Look for 4-digit years that look like wine vintages
    vintage_match = re.search(r'\b(19[5-9]\d|20[0-4]\d)\b', text)
    if vintage_match:
        year = int(vintage_match.group(1))
        # Only accept reasonable wine vintage years
        if 1950 <= year <= 2040:
            return year
    return None


def _extract_bottle_size_from_text(text: str) -> int:
    """Extract bottle size from text, defaulting to 750ml."""
    return normalize_bottle_size(text)


def _extract_last_bottle_price(text: str) -> float | None:
    """Extract LastBottle price from text, ignoring retail and best web prices."""
    # Look for "Last Bottle" followed by a price
    last_bottle_pattern = re.search(
        r'last\s+bottle[^$€£]*?([$€£]\s*[\d,]+\.?\d*)',
        text,
        re.IGNORECASE
    )
    if last_bottle_pattern:
        price_text = last_bottle_pattern.group(1)
        price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
        if price_match:
            try:
                return float(price_match.group())
            except ValueError:
                pass

    # Look for deal-related pricing patterns
    deal_patterns = [
        r'(?:deal|sale|offer|special)\s*[:\-]?\s*([$€£]\s*[\d,]+\.?\d*)',
        r'([$€£]\s*[\d,]+\.?\d*)\s*(?:deal|sale|offer|special)',
        r'(?:deal-price|sale-price|current-price|price)\D*([$€£]\s*[\d,]+\.?\d*)',
    ]

    for pattern in deal_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_text = match.group(1)
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_match:
                try:
                    return float(price_match.group())
                except ValueError:
                    continue

    # Final fallback: any price that's not explicitly marked as retail/best web
    # Split text into lines and check each for prices
    lines = text.split('\n')
    for line in lines:
        line = line.strip().lower()
        # Skip lines with retail or best web mentions
        if 'retail' in line or 'best web' in line:
            continue

        # Look for price patterns
        price_match = re.search(r'([$€£]\s*[\d,]+\.?\d*)', line)
        if price_match:
            price_text = price_match.group(1)
            price_num_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_num_match:
                try:
                    return float(price_num_match.group())
                except ValueError:
                    continue

    return None


def extract_deal_details(html: str) -> DealDetails | None:
    """
    Extract deal details from LastBottle deal page HTML.

    Args:
        html: HTML content of the deal page

    Returns:
        DealDetails instance if extraction successful, None otherwise
    """
    try:
        parser = HTMLParser(html)

        # Extract wine name
        wine_name = None

        # Try common selectors for wine names
        name_selectors = [
            'h1.product-title',
            'h1.wine-title',
            'h1.deal-title',
            '.product-name',
            '.wine-name',
            'h1',
            '.title'
        ]

        for selector in name_selectors:
            element = parser.css_first(selector)
            if element and element.text():
                wine_name = element.text().strip()
                break

        # Fallback: look for any heading with wine-like content
        if not wine_name:
            headings = parser.css('h1, h2, h3, .name, .title')
            for heading in headings:
                if heading.text():
                    text = heading.text().strip()
                    # Check if it looks like a wine name (has letters and possibly numbers)
                    if re.search(r'[a-zA-Z]{3,}', text) and len(text) > 5:
                        wine_name = text
                        break

        if not wine_name:
            return None

        # Get all text for comprehensive analysis
        all_text = parser.text()

        # Extract vintage
        vintage = _extract_vintage_from_text(all_text)

        # Extract bottle size
        bottle_size_ml = _extract_bottle_size_from_text(all_text)

        # Extract deal price (LastBottle price only)
        deal_price = _extract_last_bottle_price(all_text)

        # Also try to find price in specific elements
        if deal_price is None:
            price_selectors = [
                '.deal-price',
                '.last-bottle-price',
                '.sale-price',
                '.current-price',
                '.price',
                '.cost'
            ]

            for selector in price_selectors:
                element = parser.css_first(selector)
                if element and element.text():
                    price_text = element.text()
                    # Skip if it contains retail/best web indicators
                    if not re.search(r'retail|best\s*web', price_text, re.IGNORECASE):
                        extracted_price = _extract_last_bottle_price(price_text)
                        if extracted_price:
                            deal_price = extracted_price
                            break

        if deal_price is None:
            return None

        return DealDetails(
            wine_name=wine_name,
            vintage=vintage,
            bottle_size_ml=bottle_size_ml,
            deal_price=deal_price
        )

    except Exception:
        # Log the error in a real implementation
        return None
