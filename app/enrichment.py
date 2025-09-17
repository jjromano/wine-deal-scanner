"""Deal enrichment functionality."""

import structlog

from app.models import DealDetails, EnrichedDeal
from app.vivino import get_vivino_info

logger = structlog.get_logger(__name__)


async def enrich_deal(deal: DealDetails) -> EnrichedDeal:
    """
    Enrich a deal with Vivino data.

    Takes a DealDetails object and enriches it with Vivino rating, price,
    and review information for both the specific vintage and the wine overall.

    Args:
        deal: DealDetails object containing basic deal information

    Returns:
        EnrichedDeal object with combined deal and Vivino data
    """
    logger.info(
        "Enriching deal with Vivino data",
        wine_name=deal.wine_name,
        vintage=deal.vintage,
        deal_price=deal.deal_price
    )

    # Get Vivino data
    try:
        vivino_data = await get_vivino_info(deal.wine_name, deal.vintage)

        logger.debug(
            "Vivino data retrieved",
            wine_name=deal.wine_name,
            vintage=deal.vintage,
            has_vintage_data=any([
                vivino_data["vintage_rating"],
                vivino_data["vintage_price"],
                vivino_data["vintage_reviews"]
            ]),
            has_overall_data=any([
                vivino_data["overall_rating"],
                vivino_data["overall_price"],
                vivino_data["overall_reviews"]
            ])
        )

    except Exception as e:
        logger.warning(
            "Failed to retrieve Vivino data",
            wine_name=deal.wine_name,
            vintage=deal.vintage,
            error=str(e)
        )
        # Create empty Vivino data on failure
        vivino_data = {
            "vintage_rating": None,
            "vintage_price": None,
            "vintage_reviews": None,
            "overall_rating": None,
            "overall_price": None,
            "overall_reviews": None
        }

    # Create enriched deal
    enriched = EnrichedDeal(
        # Core deal information
        wine_name=deal.wine_name,
        vintage=deal.vintage,
        bottle_size_ml=deal.bottle_size_ml,
        deal_price=deal.deal_price,

        # Vivino vintage-specific data
        vintage_rating=vivino_data["vintage_rating"],
        vintage_price=vivino_data["vintage_price"],
        vintage_reviews=vivino_data["vintage_reviews"],

        # Vivino overall data
        overall_rating=vivino_data["overall_rating"],
        overall_price=vivino_data["overall_price"],
        overall_reviews=vivino_data["overall_reviews"]
    )

    # Log enrichment results
    if enriched.has_vivino_data:
        price_comparison = enriched.best_price_comparison
        logger.info(
            "Deal successfully enriched",
            wine_name=deal.wine_name,
            vintage=deal.vintage,
            deal_price=deal.deal_price,
            best_rating=enriched.best_rating,
            vivino_price=price_comparison["vivino_price"],
            savings=price_comparison["savings"],
            savings_percent=price_comparison["savings_percent"]
        )
    else:
        logger.info(
            "Deal enriched but no Vivino data found",
            wine_name=deal.wine_name,
            vintage=deal.vintage
        )

    return enriched

