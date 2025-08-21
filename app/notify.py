"""Telegram notification functionality."""

import asyncio

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .models import Deal, EnrichedDeal, VivinoData

logger = structlog.get_logger(__name__)


class TelegramError(Exception):
    """Exception raised when Telegram notification fails."""
    pass


def _format_deal_message(deal: Deal, vivino_data: VivinoData | None = None) -> str:
    """
    Format a deal into a Telegram message.

    Args:
        deal: Deal instance to format
        vivino_data: Optional Vivino enrichment data

    Returns:
        Formatted message string
    """
    # Start with wine details
    message_parts = [f"🍷 *{deal.title}*"]

    # Add vintage and region if available
    details = []
    if deal.vintage:
        details.append(f"📅 {deal.vintage}")
    if deal.region:
        details.append(f"📍 {deal.region}")

    if details:
        message_parts.append(" | ".join(details))

    # Add price information
    price_info = f"💰 *${deal.price:.2f}*"
    if deal.list_price and deal.list_price > deal.price:
        savings = deal.list_price - deal.price
        savings_pct = (savings / deal.list_price) * 100
        price_info += f" ~~${deal.list_price:.2f}~~ ({savings_pct:.0f}% off)"

    message_parts.append(price_info)

    # Add Vivino data if available
    if vivino_data:
        vivino_parts = []
        if vivino_data.rating is not None:
            vivino_parts.append(f"⭐ {vivino_data.rating:.1f}")
        if vivino_data.rating_count is not None:
            vivino_parts.append(f"({vivino_data.rating_count} reviews)")
        if vivino_data.avg_price is not None:
            if vivino_data.avg_price > deal.price:
                diff = vivino_data.avg_price - deal.price
                vivino_parts.append(f"📊 Avg: ${vivino_data.avg_price:.2f} (*${diff:.2f} below avg*)")
            else:
                vivino_parts.append(f"📊 Avg: ${vivino_data.avg_price:.2f}")

        if vivino_parts:
            message_parts.append(" ".join(vivino_parts))

    # Add link
    message_parts.append(f"🔗 [View Deal]({deal.url})")

    return "\n\n".join(message_parts)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
async def _send_telegram_message(
    client: httpx.AsyncClient,
    message: str,
    chat_id: str,
    bot_token: str
) -> bool:
    """
    Send a message via Telegram API with retry logic.

    Args:
        client: HTTP client instance
        message: Message text to send
        chat_id: Telegram chat ID
        bot_token: Telegram bot token

    Returns:
        True if message sent successfully

    Raises:
        TelegramError: If sending fails after retries
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            raise TelegramError(f"Telegram API error: {result.get('description', 'Unknown error')}")

        return True

    except httpx.HTTPError as e:
        raise TelegramError(f"HTTP error sending Telegram message: {e}")
    except ValueError as e:
        raise TelegramError(f"Invalid JSON response from Telegram: {e}")


async def telegram_send(
    deal: Deal,
    vivino_data: VivinoData | None = None,
    timeout_s: float = 10.0
) -> bool:
    """
    Send a deal notification via Telegram.

    Args:
        deal: Deal to notify about
        vivino_data: Optional Vivino enrichment data
        timeout_s: Request timeout in seconds

    Returns:
        True if notification sent successfully, False otherwise
    """
    try:
        async with asyncio.timeout(timeout_s):
            message = _format_deal_message(deal, vivino_data)

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_s)
            ) as client:
                return await _send_telegram_message(
                    client, message, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
                )

    except TimeoutError:
        # Timeout exceeded
        return False
    except TelegramError:
        # Telegram API error
        return False
    except Exception:
        # Any other error
        return False


def _format_enriched_deal_message(enriched_deal: EnrichedDeal) -> str:
    """
    Format an enriched deal into a Telegram message.

    Args:
        enriched_deal: EnrichedDeal instance to format

    Returns:
        Formatted message string
    """
    # Build the main deal information
    message_parts = []

    # Header with wine name and vintage
    vintage_str = f" {enriched_deal.vintage}" if enriched_deal.vintage else ""
    header = f"🍷 New Deal: {enriched_deal.wine_name}{vintage_str}"
    message_parts.append(header)

    # Size information
    size_info = f"Size: {enriched_deal.bottle_size_ml}ml"
    message_parts.append(size_info)

    # Deal price
    price_info = f"Deal Price: ${enriched_deal.deal_price:.2f}"
    message_parts.append(price_info)

    # Add empty line before Vivino data
    message_parts.append("")

    # Vivino vintage-specific data
    if enriched_deal.vintage_rating or enriched_deal.vintage_price or enriched_deal.vintage_reviews:
        vintage_parts = []

        if enriched_deal.vintage_rating:
            vintage_parts.append(f"{enriched_deal.vintage_rating:.1f}⭐")

        if enriched_deal.vintage_price:
            vintage_parts.append(f"avg (${enriched_deal.vintage_price:.2f})")

        if enriched_deal.vintage_reviews:
            vintage_parts.append(f"{enriched_deal.vintage_reviews} reviews")

        if vintage_parts:
            vintage_line = f"Vivino (vintage): {' — '.join(vintage_parts)}"
            message_parts.append(vintage_line)

    # Vivino overall data
    if enriched_deal.overall_rating or enriched_deal.overall_price or enriched_deal.overall_reviews:
        overall_parts = []

        if enriched_deal.overall_rating:
            overall_parts.append(f"{enriched_deal.overall_rating:.1f}⭐")

        if enriched_deal.overall_price:
            overall_parts.append(f"avg (${enriched_deal.overall_price:.2f})")

        if enriched_deal.overall_reviews:
            overall_parts.append(f"{enriched_deal.overall_reviews} reviews")

        if overall_parts:
            overall_line = f"Vivino (overall): {' — '.join(overall_parts)}"
            message_parts.append(overall_line)

    # Add savings information if available
    price_comparison = enriched_deal.best_price_comparison
    if price_comparison["savings"] and price_comparison["savings"] > 0:
        savings_pct = price_comparison["savings_percent"]
        savings_line = f"💰 Save ${price_comparison['savings']:.2f} ({savings_pct:.1f}% off Vivino avg)"
        message_parts.append("")
        message_parts.append(savings_line)

    return "\n".join(message_parts)


async def send_telegram_message(
    enriched_deal: EnrichedDeal,
    timeout_s: float = 10.0
) -> bool:
    """
    Send an enriched deal notification via Telegram.

    Args:
        enriched_deal: EnrichedDeal to notify about
        timeout_s: Request timeout in seconds

    Returns:
        True if notification sent successfully, False otherwise
    """
    logger.info(
        "Sending Telegram notification",
        wine_name=enriched_deal.wine_name,
        vintage=enriched_deal.vintage,
        deal_price=enriched_deal.deal_price,
        has_vivino_data=enriched_deal.has_vivino_data
    )

    try:
        async with asyncio.timeout(timeout_s):
            message = _format_enriched_deal_message(enriched_deal)

            logger.debug(
                "Formatted Telegram message",
                message_length=len(message),
                wine_name=enriched_deal.wine_name
            )

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_s)
            ) as client:
                success = await _send_telegram_message(
                    client, message, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN
                )

                if success:
                    logger.info(
                        "Telegram notification sent successfully",
                        wine_name=enriched_deal.wine_name,
                        vintage=enriched_deal.vintage,
                        chat_id=TELEGRAM_CHAT_ID
                    )
                else:
                    logger.error(
                        "Failed to send Telegram notification",
                        wine_name=enriched_deal.wine_name,
                        vintage=enriched_deal.vintage
                    )

                return success

    except TimeoutError:
        logger.warning(
            "Telegram notification timed out",
            wine_name=enriched_deal.wine_name,
            timeout_seconds=timeout_s
        )
        return False
    except TelegramError as e:
        logger.error(
            "Telegram API error",
            wine_name=enriched_deal.wine_name,
            error=str(e)
        )
        return False
    except Exception as e:
        logger.error(
            "Unexpected error sending Telegram notification",
            wine_name=enriched_deal.wine_name,
            error=str(e)
        )
        return False
