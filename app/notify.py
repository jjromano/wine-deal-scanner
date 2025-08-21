"""Telegram notification functionality."""

import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .models import Deal, VivinoData


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
