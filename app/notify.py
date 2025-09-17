from app import config
from app.models import EnrichedDeal

def _fmt_triplet(t):
    # t = (rating, count, avg_price, url) or (None,...)
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
    import httpx, os
    from urllib.parse import quote
    
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


# Backward compatibility functions for tests
class TelegramError(Exception):
    """Exception for Telegram API errors."""
    pass


def _format_enriched_deal_message(enriched: EnrichedDeal) -> str:
    """Format enriched deal for Telegram message."""
    lines = []
    
    # Header
    vintage_str = f" {enriched.vintage}" if enriched.vintage else ""
    lines.append(f"🍷 New Deal: {enriched.wine_name}{vintage_str}")
    
    # Basic info
    size_str = f"{enriched.bottle_size_ml}ml" if enriched.bottle_size_ml != 750 else "750ml"
    lines.append(f"Size: {size_str}")
    lines.append(f"Deal Price: ${enriched.deal_price:.2f}")
    
    # Vivino data
    if enriched.vintage_rating or enriched.vintage_price or enriched.vintage_reviews:
        rating_str = f"{enriched.vintage_rating:.1f}⭐" if enriched.vintage_rating else "—"
        price_str = f"avg (${enriched.vintage_price:.2f})" if enriched.vintage_price else "—"
        reviews_str = f"{enriched.vintage_reviews} reviews" if enriched.vintage_reviews else "— reviews"
        lines.append(f"Vivino (vintage): {rating_str} — {price_str} — {reviews_str}")
    
    if enriched.overall_rating or enriched.overall_price or enriched.overall_reviews:
        rating_str = f"{enriched.overall_rating:.1f}⭐" if enriched.overall_rating else "—"
        price_str = f"avg (${enriched.overall_price:.2f})" if enriched.overall_price else "—"
        reviews_str = f"{enriched.overall_reviews} reviews" if enriched.overall_reviews else "— reviews"
        lines.append(f"Vivino (overall): {rating_str} — {price_str} — {reviews_str}")
    
    # Savings calculation
    price_comparison = enriched.best_price_comparison
    if price_comparison["savings"] and price_comparison["savings"] > 0:
        savings = price_comparison["savings"]
        savings_percent = price_comparison["savings_percent"]
        lines.append(f"💰 Save ${savings:.2f} ({savings_percent:.1f}% off Vivino avg)")
    
    return "\n".join(lines)


async def send_telegram_message(enriched: EnrichedDeal) -> bool:
    """Send Telegram message for enriched deal."""
    try:
        import httpx, os
        
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        if not token or not chat_id:
            if config.DEBUG:
                print("[notify] Missing Telegram credentials")
            return False
        
        message = _format_enriched_deal_message(enriched)
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message}
            )
            
            if response.status_code != 200:
                raise TelegramError(f"HTTP {response.status_code}: {response.text}")
            
            if config.DEBUG:
                print(f"[notify] Telegram message sent successfully: {response.status_code}")
            
            return True
            
    except Exception as e:
        if config.DEBUG:
            print(f"[notify] send_telegram_message error: {e}")
        return False