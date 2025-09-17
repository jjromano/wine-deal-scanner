import re
from app import config
from app.domutils import extract_from_cta
from app.models import Deal, DealDetails, normalize_bottle_size

async def extract_deal_from_dom(page):
    # First try CTA-scoped extraction
    title, price = await extract_from_cta(page)

    # If title is generic, try a more specific set of selectors
    if config.is_generic_title(title):
        title2 = await page.evaluate("""
          () => {
            const sels=['.product-title','.deal-title','h1.product-title','h1.title','h1','h2'];
            for (const s of sels){ const el=document.querySelector(s); if (el?.innerText?.trim()) return el.innerText.trim(); }
            return (document.title || '').trim();
          }
        """)
        title = title2 or title

    # Normalize price: ignore junk < $5
    if price is not None and price < 5.0:
        price = None

    size_ml = 750  # default
    # Try to detect uncommon sizes if shown in text
    try:
        s = await page.evaluate("() => document.body?.innerText || ''")
        if "375ml" in s.lower(): size_ml = 375
        elif "1.5l" in s.lower() or "magnum" in s.lower(): size_ml = 1500
    except:
        pass

    if config.DEBUG:
        print(f"[dom.peek] title={title!r} price={price}")

    if not title:
        return None
    return Deal(title=title.strip(), price=(price or 0.0), bottle_size_ml=size_ml, url=config.LASTBOTTLE_URL)


# Backward compatibility functions for tests
def deal_key(wine_name: str, vintage: str | int | None = None, price: float | None = None) -> str:
    """Generate a unique key for deal deduplication."""
    # Normalize wine name
    name = (wine_name or "").strip().lower()
    # Replace accented characters
    name = re.sub(r'[àáâãäå]', 'a', name)
    name = re.sub(r'[èéêë]', 'e', name)
    name = re.sub(r'[ìíîï]', 'i', name)
    name = re.sub(r'[òóôõö]', 'o', name)
    name = re.sub(r'[ùúûü]', 'u', name)
    name = re.sub(r'[ñ]', 'n', name)
    name = re.sub(r'[ç]', 'c', name)
    # Remove special chars
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()  # Normalize whitespace
    
    # Format vintage - handle both string and int
    if vintage is None:
        vintage_str = "unknown"
    else:
        vintage_str = str(vintage)
    
    # Format price
    price_str = f"{price:.2f}" if price is not None else ""
    
    # Create key
    key = f"{name}|{vintage_str}|{price_str}"
    return key


async def parse_deal_from_html(html: str) -> DealDetails | None:
    """Parse deal details from HTML content."""
    if not html:
        return None
    
    # Extract wine name from title or h1
    wine_name = None
    
    # Try title tag
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    if title_match:
        wine_name = title_match.group(1).strip()
    
    # Try h1 tags
    if not wine_name or config.is_generic_title(wine_name):
        h1_matches = re.findall(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        for h1 in h1_matches:
            if not config.is_generic_title(h1.strip()):
                wine_name = h1.strip()
                break
    
    if not wine_name or config.is_generic_title(wine_name):
        return None
    
    # Extract vintage year
    vintage = None
    vintage_match = re.search(r'\b(19|20)\d{2}\b', wine_name)
    if vintage_match:
        try:
            vintage = int(vintage_match.group(0))
        except:
            pass
    
    # Extract price
    price = None
    price_patterns = [
        r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',
        r'price["\']?\s*:\s*["\']?\$?([0-9]+(?:\.[0-9]{2})?)',
        r'deal["\']?\s*:\s*["\']?\$?([0-9]+(?:\.[0-9]{2})?)'
    ]
    
    for pattern in price_patterns:
        match = re.search(pattern, html, re.I)
        if match:
            try:
                price = float(match.group(1).replace(',', ''))
                if price >= 5.0:  # Valid price
                    break
                else:
                    price = None
            except:
                pass
    
    if not price:
        return None
    
    # Extract bottle size
    bottle_size_ml = normalize_bottle_size(wine_name + " " + html[:1000])
    
    return DealDetails(
        wine_name=wine_name,
        vintage=vintage,
        bottle_size_ml=bottle_size_ml,
        deal_price=price
    )


def extract_deal_from_json(json_data: dict) -> Deal | None:
    """Extract deal from JSON data (backward compatibility)."""
    if not json_data:
        return None
    
    # Try to extract basic info
    title = json_data.get("name") or json_data.get("title") or json_data.get("wine_name")
    price = json_data.get("price") or json_data.get("deal_price") or json_data.get("current_price")
    
    if not title or not price:
        return None
    
    # Try to extract other fields
    vintage = json_data.get("vintage")
    size_ml = json_data.get("bottle_size_ml", 750)
    url = json_data.get("url", config.LASTBOTTLE_URL)
    
    try:
        price_float = float(price)
        if price_float < 5.0:
            return None
    except:
        return None
    
    return Deal(
        title=str(title).strip(),
        price=price_float,
        vintage=str(vintage) if vintage else None,
        bottle_size_ml=int(size_ml),
        url=str(url)
    )


def pick_lastbottle_price(text: str) -> float | None:
    """Pick LastBottle price from text (backward compatibility)."""
    if not text:
        return None
    
    # Use similar logic to domutils
    price_patterns = [
        r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)',
        r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*\$'
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                price = float(match.replace(',', ''))
                if price >= 5.0:
                    return price
            except:
                continue
    
    return None


def extract_deal_details(html: str) -> DealDetails | None:
    """Alias for parse_deal_from_html (backward compatibility)."""
    return parse_deal_from_html(html)