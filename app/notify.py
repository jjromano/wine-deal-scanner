"""Telegram notification functionality."""

import httpx
import os
from urllib.parse import quote
from app import config


def _fmt_triplet(t):
    """Format Vivino data triplet (rating, count, avg_price, url) for display."""
    if not t or not isinstance(t, tuple):
        return None  # Return None to indicate no data (line will be removed)
    
    r, c, p, _ = (list(t) + [None, None, None, None])[:4]
    
    # If we have no meaningful data, return None to remove the line
    if not any([r, c, p]):
        return None
    
    parts = []
    parts.append(f"{r:.1f} ⭐" if isinstance(r, (int, float)) else "—")
    parts.append(f"({c} reviews)" if isinstance(c, int) else "")
    parts.append(f"~ ${p:.0f}" if isinstance(p, (int, float)) else "")
    out = " ".join(filter(None, parts)).strip()
    return out if out else None


async def telegram_send(deal, vivino_data):
    """Send Telegram notification for a wine deal."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Handle new format with vintage year
    if vivino_data and len(vivino_data) >= 3:
        vintage, overall, vintage_year = vivino_data
    else:
        vintage, overall, vintage_year = (vivino_data or (None, None)) + (None,)
    
    # Check if this is a non-vintage wine
    is_non_vintage = ' NV' in (deal.title or '') or ' Non-Vintage' in (deal.title or '') or ' non-vintage' in (deal.title or '')

    price_line = "Price: " + (f"${deal.price:.2f}" if config.is_price_valid(getattr(deal,'price',0)) else "—")
    
    # Generate Vivino search link (always shown at end)
    wine_title = deal.title or ""
    vivino_search_link = f"https://www.vivino.com/search/wines?q={quote(wine_title)}"
    
    # Try to get direct wine links from the Vivino data
    direct_vintage_link = None
    direct_overall_link = None
    
    if vintage and len(vintage) > 3 and vintage[3]:
        direct_vintage_link = vintage[3]
    if overall and len(overall) > 3 and overall[3]:
        direct_overall_link = overall[3]
    
    # Use direct link if available, otherwise use search link
    final_vivino_link = direct_vintage_link or direct_overall_link or vivino_search_link
    
    # Format rating lines (only include if data is available)
    lines = [
        "🍷 New LastBottle Deal",
        wine_title or "—",
        f"Size: {getattr(deal,'bottle_size_ml',750)} ml",
        price_line,
    ]
    
    # For non-vintage wines, only show overall data (no vintage-specific line)
    if is_non_vintage:
        # For NV wines, show overall data as the main Vivino data
        overall_formatted = _fmt_triplet(overall)
        if overall_formatted:
            lines.append(f"Vivino: {overall_formatted}")
    else:
        # For vintage wines, show both vintage and overall data
        # Add vintage line only if we have data
        if vintage_year:
            vintage_formatted = _fmt_triplet(vintage)
            if vintage_formatted:
                lines.append(f"Vivino ({vintage_year}): {vintage_formatted}")
        
        # Add overall line only if we have data
        overall_formatted = _fmt_triplet(overall)
        if overall_formatted:
            lines.append(f"Vivino (All): {overall_formatted}")
    
    # Always add LastBottle link
    lines.append(f"LastBottle: {getattr(deal,'url','https://www.lastbottlewines.com/')}")
    
    # Always add Vivino link at the end
    lines.append(f"Vivino: {final_vivino_link}")
    
    text = "\n".join(lines)

    if config.DEBUG:
        print("[notify] preview:", text[:120])

    if token and chat_id:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                  json={"chat_id": chat_id, "text": text})
            if config.DEBUG:
                print("[notify] status:", r.status_code, "body:", r.text)
            return True, r.status_code, r.text
    return False, 0, ""