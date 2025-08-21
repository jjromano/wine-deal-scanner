"""Vivino data lookup functionality."""

import asyncio
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from .config import VIVINO_TIMEOUT_SECONDS


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


@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(0.5),
    reraise=True
)
async def _search_vivino(
    client: httpx.AsyncClient,
    wine_name: str,
    vintage: str | None = None
) -> dict | None:
    """
    Search Vivino for wine data with retry logic.

    Args:
        client: HTTP client instance
        wine_name: Name of the wine to search
        vintage: Optional vintage year

    Returns:
        Vivino search result data or None if not found
    """
    # Build search query
    search_query = _normalize_wine_name(wine_name)
    if vintage:
        search_query = f"{search_query} {vintage}"

    # Vivino search API (this is a simplified approach)
    # In reality, you might need to:
    # 1. Use Vivino's actual API if available
    # 2. Scrape their search results (be mindful of rate limits and ToS)
    # 3. Use a different wine database API

    search_url = "https://www.vivino.com/api/wines/search"
    params = {
        "q": search_query,
        "per_page": 5,
    }

    try:
        response = await client.get(search_url, params=params)
        response.raise_for_status()

        data = response.json()
        wines = data.get("matches", [])

        if not wines:
            return None

        # Return the first match (most relevant)
        # TODO: Implement better matching logic based on name similarity
        return wines[0]

    except (httpx.HTTPError, ValueError) as e:
        raise VivinoLookupError(f"Failed to search Vivino: {e}")


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
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_s),
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
            ) as client:
                wine_data = await _search_vivino(client, name, vintage)

                if not wine_data:
                    return None, None, None

                # Extract data from Vivino response
                # TODO: Update these field mappings based on actual Vivino API structure
                wine = wine_data.get("wine", {})

                rating = wine.get("average_rating")
                rating_count = wine.get("ratings_count")

                # Price data might be in a different structure
                price_data = wine.get("price", {})
                avg_price = None
                if price_data:
                    avg_price = price_data.get("amount")

                return rating, rating_count, avg_price

    except TimeoutError:
        # Timeout exceeded, return empty data
        return None, None, None
    except VivinoLookupError:
        # Lookup failed, return empty data
        return None, None, None
    except Exception:
        # Any other error, return empty data to maintain strict timeout
        return None, None, None
