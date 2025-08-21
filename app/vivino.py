"""Vivino data lookup functionality."""

import asyncio
import re
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import VIVINO_TIMEOUT_SECONDS

logger = structlog.get_logger(__name__)


class VivinoLookupError(Exception):
    """Exception raised when Vivino lookup fails."""
    pass


def _normalize_wine_name(name: str) -> str:
    """
    Normalize wine name for better Vivino search matching.

    Args:
        name: Original wine name

    Returns:
        Normalized wine name for search
    """
    # Remove common wine terms that might interfere with search
    normalized = re.sub(r'\b(wine|red|white|rose|rosé|sparkling)\b', '', name, flags=re.IGNORECASE)

    # Remove extra spaces and clean up
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def parse_vivino_page(html: str) -> tuple[float | None, int | None, float | None]:
    """
    Pure parser function to extract wine data from Vivino HTML page.

    Args:
        html: Raw HTML content from Vivino wine page

    Returns:
        Tuple of (rating, rating_count, avg_price) - all optional
    """
    rating = None
    rating_count = None
    avg_price = None

    try:
        # Extract rating - look for common patterns in Vivino pages (in priority order)
        # Pattern 1: JSON-LD structured data
        rating_match = re.search(r'"ratingValue":\s*"?([0-9.]+)"?', html)
        if rating_match:
            rating = float(rating_match.group(1))

        # Pattern 2: Meta property for rating
        if rating is None:
            rating_match = re.search(r'<meta[^>]*property="vivino:rating"[^>]*content="([0-9.]+)"', html)
            if rating_match:
                rating = float(rating_match.group(1))

        # Pattern 3: Data attribute or class-based rating
        if rating is None:
            rating_match = re.search(r'data-rating="([0-9.]+)"', html)
            if rating_match:
                rating = float(rating_match.group(1))

        # Extract rating count - look for review/rating count patterns (in priority order)
        # Pattern 1: JSON-LD review count
        count_match = re.search(r'"reviewCount":\s*"?([0-9,]+)"?', html)
        if count_match:
            rating_count = int(count_match.group(1).replace(',', ''))

        # Pattern 2: Meta property for rating count
        if rating_count is None:
            count_match = re.search(r'<meta[^>]*property="vivino:rating_count"[^>]*content="([0-9,]+)"', html)
            if count_match:
                rating_count = int(count_match.group(1).replace(',', ''))

        # Pattern 3: Text-based rating count (e.g., "1,234 ratings")
        if rating_count is None:
            count_match = re.search(r'([0-9,]+)\s*(?:ratings?|reviews?)', html, re.IGNORECASE)
            if count_match:
                rating_count = int(count_match.group(1).replace(',', ''))

        # Extract average price - look for price patterns (in priority order)
        # Pattern 1: JSON-LD price
        price_match = re.search(r'"price":\s*"?\$?([0-9,]+\.?[0-9]*)"?', html)
        if price_match:
            avg_price = float(price_match.group(1).replace(',', ''))

        # Pattern 2: Meta property for price
        if avg_price is None:
            price_match = re.search(r'<meta[^>]*property="vivino:price"[^>]*content="\$?([0-9,]+\.?[0-9]*)"', html)
            if price_match:
                avg_price = float(price_match.group(1).replace(',', ''))

        # Pattern 3: Data attribute or class-based price
        if avg_price is None:
            price_match = re.search(r'data-price="?\$?([0-9,]+\.?[0-9]*)"?', html)
            if price_match:
                avg_price = float(price_match.group(1).replace(',', ''))

        # Pattern 4: Text-based price patterns (e.g., "Average price: $1,250.99")
        if avg_price is None:
            price_match = re.search(r'(?:average\s+price|price):\s*\$?([0-9,]+\.?[0-9]*)', html, re.IGNORECASE)
            if price_match:
                avg_price = float(price_match.group(1).replace(',', ''))

    except (ValueError, TypeError) as e:
        logger.debug("Error parsing Vivino page", error=str(e))

    logger.debug(
        "Parsed Vivino page",
        rating=rating,
        rating_count=rating_count,
        avg_price=avg_price
    )

    return rating, rating_count, avg_price


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True
)
async def resolve_vivino_url(query: str, timeout_s: float = 1.5) -> str | None:
    """
    Network layer: Resolve a Vivino search query to a wine page URL.

    Args:
        query: Search query for the wine
        timeout_s: Timeout in seconds for the request

    Returns:
        URL of the wine page, or None if not found
    """
    logger.debug("Resolving Vivino URL", query=query, timeout=timeout_s)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_s),
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.vivino.com/"
            }
        ) as client:
            # Try Vivino search page
            search_url = "https://www.vivino.com/search/wines"
            params = {"q": query}

            response = await client.get(search_url, params=params)
            response.raise_for_status()

            html = response.text

            # Extract the first wine URL from search results
            # Look for wine page links in the HTML
            wine_url_patterns = [
                r'<a[^>]*href="(/wines/[^"]+)"[^>]*>',
                r'href="(https://www\.vivino\.com/wines/[^"]+)"',
                r'"url":"(https://www\.vivino\.com/wines/[^"]+)"',
                r'"url":"(/wines/[^"]+)"'
            ]

            for pattern in wine_url_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    wine_path = matches[0]
                    # Ensure we have a full URL
                    if wine_path.startswith('/'):
                        wine_url = f"https://www.vivino.com{wine_path}"
                    else:
                        wine_url = wine_path

                    logger.debug("Found Vivino wine URL", query=query, url=wine_url)
                    return wine_url

            logger.debug("No wine URL found in search results", query=query)
            return None

    except httpx.HTTPError as e:
        logger.debug("HTTP error resolving Vivino URL", query=query, error=str(e))
        raise VivinoLookupError(f"Failed to resolve Vivino URL: {e}")
    except Exception as e:
        logger.debug("Unexpected error resolving Vivino URL", query=query, error=str(e))
        raise VivinoLookupError(f"Unexpected error resolving Vivino URL: {e}")


async def _fetch_vivino_page(url: str, timeout_s: float = 1.5) -> str:
    """
    Fetch the HTML content of a Vivino wine page.

    Args:
        url: URL of the Vivino wine page
        timeout_s: Timeout in seconds for the request

    Returns:
        HTML content of the page
    """
    logger.debug("Fetching Vivino page", url=url, timeout=timeout_s)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_s),
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.vivino.com/"
        }
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def quick_lookup(
    name: str,
    vintage: str | None = None,
    timeout_s: float = VIVINO_TIMEOUT_SECONDS
) -> tuple[float | None, int | None, float | None]:
    """
    Quick Vivino lookup with strict timeout budget.

    Args:
        name: Wine name to search for
        vintage: Optional vintage year
        timeout_s: Timeout in seconds (default from config)

    Returns:
        Tuple of (rating, rating_count, avg_price) - all optional
    """
    try:
        async with asyncio.timeout(timeout_s):
            # Normalize and build search query
            normalized_name = _normalize_wine_name(name)
            query = f"{normalized_name} {vintage}" if vintage else normalized_name

            # Network layer: resolve URL
            wine_url = await resolve_vivino_url(query, timeout_s * 0.6)  # Use 60% of timeout for URL resolution
            if not wine_url:
                return None, None, None

            # Network layer: fetch page content
            html = await _fetch_vivino_page(wine_url, timeout_s * 0.4)  # Use 40% of timeout for page fetch

            # Parser layer: extract data from HTML
            return parse_vivino_page(html)

    except TimeoutError:
        logger.debug("Quick lookup timed out", name=name, vintage=vintage, timeout=timeout_s)
        return None, None, None
    except VivinoLookupError:
        logger.debug("Quick lookup failed", name=name, vintage=vintage)
        return None, None, None
    except Exception as e:
        logger.debug("Quick lookup error", name=name, vintage=vintage, error=str(e))
        return None, None, None


async def quick_lookup_comprehensive(
    name: str,
    vintage: str | None = None,
    timeout_s: float = VIVINO_TIMEOUT_SECONDS
) -> dict[str, tuple[float | None, int | None, float | None]]:
    """
    Comprehensive Vivino lookup using the new layered approach.

    Args:
        name: Wine name to search for
        vintage: Optional vintage year
        timeout_s: Timeout in seconds (default from config)

    Returns:
        Dict with keys:
        - "vintage": Tuple of (rating, rating_count, avg_price) for vintage search
        - "all": Tuple of (rating, rating_count, avg_price) for general search
    """
    result = {
        "vintage": (None, None, None),
        "all": (None, None, None)
    }

    try:
        async with asyncio.timeout(timeout_s):
            # Normalize wine name
            normalized_name = _normalize_wine_name(name)

            # Search with vintage if provided
            if vintage:
                vintage_query = f"{normalized_name} {vintage}"
                try:
                    # Network layer: resolve URL
                    wine_url = await resolve_vivino_url(vintage_query, timeout_s * 0.3)
                    if wine_url:
                        # Network layer: fetch page content
                        html = await _fetch_vivino_page(wine_url, timeout_s * 0.2)
                        # Parser layer: extract data from HTML
                        result["vintage"] = parse_vivino_page(html)
                except Exception:
                    pass  # Continue to general search

            # General search (without vintage)
            try:
                # Network layer: resolve URL
                wine_url = await resolve_vivino_url(normalized_name, timeout_s * 0.3)
                if wine_url:
                    # Network layer: fetch page content
                    html = await _fetch_vivino_page(wine_url, timeout_s * 0.2)
                    # Parser layer: extract data from HTML
                    result["all"] = parse_vivino_page(html)
            except Exception:
                pass  # Return whatever we have

    except TimeoutError:
        logger.debug("Quick lookup comprehensive timed out", name=name, vintage=vintage, timeout=timeout_s)
    except Exception as e:
        logger.debug("Quick lookup comprehensive error", name=name, vintage=vintage, error=str(e))

    return result


def _extract_wine_data(wine_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extract rating, price, and review data from Vivino wine data.

    Args:
        wine_data: Raw wine data from Vivino API

    Returns:
        Dict with extracted data: rating, price, reviews
    """
    extracted = {
        "rating": None,
        "price": None,
        "reviews": None
    }

    try:
        # Extract wine information - handle various possible structures
        wine = wine_data.get("wine", wine_data)

        # Extract rating
        rating = wine.get("average_rating") or wine.get("rating") or wine.get("score")
        if rating is not None:
            extracted["rating"] = float(rating)

        # Extract review count
        reviews = (
            wine.get("ratings_count") or
            wine.get("reviews_count") or
            wine.get("num_reviews") or
            wine.get("review_count")
        )
        if reviews is not None:
            extracted["reviews"] = int(reviews)

        # Extract price - try multiple possible structures
        price = None

        # Direct price fields
        price = wine.get("price") or wine.get("average_price")

        # Nested price structure
        if price is None:
            price_data = wine.get("price_data") or wine.get("pricing")
            if isinstance(price_data, dict):
                price = price_data.get("amount") or price_data.get("price")

        # Statistics structure
        if price is None:
            stats = wine.get("statistics") or wine.get("stats")
            if isinstance(stats, dict):
                price = stats.get("average_price") or stats.get("price")

        if price is not None:
            extracted["price"] = float(price)

    except (ValueError, TypeError) as e:
        logger.debug("Error extracting wine data", error=str(e), wine_data=wine_data)

    return extracted


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
async def _search_vivino_comprehensive(
    client: httpx.AsyncClient,
    query: str,
    search_type: str = "general"
) -> dict[str, Any] | None:
    """
    Search Vivino with comprehensive retry logic.

    Args:
        client: HTTP client instance
        query: Search query string
        search_type: Type of search for logging ("vintage" or "general")

    Returns:
        Best matching wine data or None if not found
    """
    logger.debug("Searching Vivino", query=query, search_type=search_type)

    # Try multiple possible Vivino endpoints
    endpoints = [
        "https://www.vivino.com/api/wines/search",
        "https://www.vivino.com/search/wines",
        "https://api.vivino.com/wines/search"  # Alternative API endpoint
    ]

    for endpoint in endpoints:
        try:
            params = {
                "q": query,
                "per_page": 10,  # Get more results for better matching
                "order_by": "ratings_count",  # Prefer wines with more reviews
                "order": "desc"
            }

            response = await client.get(endpoint, params=params)
            response.raise_for_status()

            data = response.json()

            # Handle different response structures
            wines = data.get("matches") or data.get("results") or data.get("wines") or []

            if wines:
                logger.debug(
                    "Vivino search successful",
                    query=query,
                    search_type=search_type,
                    results_count=len(wines),
                    endpoint=endpoint
                )

                # Return the first (most relevant) result
                return wines[0]

        except httpx.HTTPError as e:
            logger.debug(
                "Vivino endpoint failed",
                endpoint=endpoint,
                error=str(e),
                search_type=search_type
            )
            continue
        except (ValueError, KeyError) as e:
            logger.debug(
                "Vivino response parsing failed",
                endpoint=endpoint,
                error=str(e),
                search_type=search_type
            )
            continue

    logger.debug("No Vivino results found", query=query, search_type=search_type)
    return None


async def get_vivino_info(wine_name: str, vintage: int | None = None) -> dict[str, Any]:
    """
    Get comprehensive Vivino information for a wine.

    Performs two searches:
    1. With vintage (if provided): "Wine Name YYYY"
    2. Without vintage: "Wine Name"

    Args:
        wine_name: Name of the wine to search for
        vintage: Optional vintage year

    Returns:
        Dict with keys:
        - vintage_rating: Rating for specific vintage (if vintage provided)
        - vintage_price: Price for specific vintage (if vintage provided)
        - vintage_reviews: Review count for specific vintage (if vintage provided)
        - overall_rating: Rating for wine in general
        - overall_price: Price for wine in general
        - overall_reviews: Review count for wine in general
    """
    result = {
        "vintage_rating": None,
        "vintage_price": None,
        "vintage_reviews": None,
        "overall_rating": None,
        "overall_price": None,
        "overall_reviews": None
    }

    normalized_name = _normalize_wine_name(wine_name)

    logger.info(
        "Starting Vivino lookup",
        wine_name=wine_name,
        vintage=vintage,
        normalized_name=normalized_name
    )

    try:
        async with asyncio.timeout(VIVINO_TIMEOUT_SECONDS * 2):  # Allow more time for dual search
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(VIVINO_TIMEOUT_SECONDS),
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.vivino.com/"
                }
            ) as client:

                # Search 1: With vintage (if provided)
                if vintage:
                    vintage_query = f"{normalized_name} {vintage}"
                    logger.debug("Performing vintage-specific search", query=vintage_query)

                    try:
                        vintage_data = await _search_vivino_comprehensive(
                            client, vintage_query, "vintage"
                        )

                        if vintage_data:
                            vintage_info = _extract_wine_data(vintage_data)
                            result["vintage_rating"] = vintage_info["rating"]
                            result["vintage_price"] = vintage_info["price"]
                            result["vintage_reviews"] = vintage_info["reviews"]

                            logger.info(
                                "Vintage-specific data found",
                                vintage=vintage,
                                rating=vintage_info["rating"],
                                price=vintage_info["price"],
                                reviews=vintage_info["reviews"]
                            )
                        else:
                            logger.debug("No vintage-specific results found", vintage=vintage)

                    except Exception as e:
                        logger.warning(
                            "Vintage search failed",
                            vintage=vintage,
                            error=str(e)
                        )

                # Search 2: General wine search (without vintage)
                logger.debug("Performing general wine search", query=normalized_name)

                try:
                    general_data = await _search_vivino_comprehensive(
                        client, normalized_name, "general"
                    )

                    if general_data:
                        general_info = _extract_wine_data(general_data)
                        result["overall_rating"] = general_info["rating"]
                        result["overall_price"] = general_info["price"]
                        result["overall_reviews"] = general_info["reviews"]

                        logger.info(
                            "General wine data found",
                            rating=general_info["rating"],
                            price=general_info["price"],
                            reviews=general_info["reviews"]
                        )
                    else:
                        logger.debug("No general results found")

                except Exception as e:
                    logger.warning("General search failed", error=str(e))

                # Log final results
                found_data = any([
                    result["vintage_rating"], result["vintage_price"], result["vintage_reviews"],
                    result["overall_rating"], result["overall_price"], result["overall_reviews"]
                ])

                if found_data:
                    logger.info(
                        "Vivino lookup completed successfully",
                        wine_name=wine_name,
                        vintage=vintage,
                        has_vintage_data=any([
                            result["vintage_rating"],
                            result["vintage_price"],
                            result["vintage_reviews"]
                        ]),
                        has_general_data=any([
                            result["overall_rating"],
                            result["overall_price"],
                            result["overall_reviews"]
                        ])
                    )
                else:
                    logger.warning(
                        "No Vivino data found",
                        wine_name=wine_name,
                        vintage=vintage
                    )

    except TimeoutError:
        logger.warning(
            "Vivino lookup timed out",
            wine_name=wine_name,
            vintage=vintage,
            timeout_seconds=VIVINO_TIMEOUT_SECONDS * 2
        )
    except Exception as e:
        logger.error(
            "Vivino lookup failed",
            wine_name=wine_name,
            vintage=vintage,
            error=str(e)
        )

    return result
