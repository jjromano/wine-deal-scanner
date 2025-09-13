from app import config

def _fmt_triplet(t):
    # t = (rating, count, avg_price, url) or (None,...)
    if not t or not isinstance(t, tuple):
        return "—"
    r, c, p, _ = (list(t) + [None, None, None, None])[:4]
    parts = []
    parts.append(f"{r:.1f} ⭐" if isinstance(r, (int, float)) else "—")
    parts.append(f"({c} reviews)" if isinstance(c, int) else "")
    parts.append(f"~ ${p:.0f}" if isinstance(p, (int, float)) else "")
    out = " ".join(filter(None, parts)).strip()
    return out if out else "—"

async def telegram_send(deal, vivino_data):
    import httpx, os
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    vintage, overall = vivino_data or (None, None)

    price_line = "Price: " + (f"${deal.price:.2f}" if config.is_price_valid(getattr(deal,'price',0)) else "—")
    lines = [
        "🍷 New LastBottle Deal",
        deal.title or "—",
        f"Size: {getattr(deal,'bottle_size_ml',750)} ml",
        price_line,
        f"Vivino (Vintage): {_fmt_triplet(vintage)}",
        f"Vivino (All): {_fmt_triplet(overall)}",
        f"Link: {getattr(deal,'url','https://www.lastbottlewines.com/')}",
    ]
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