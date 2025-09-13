from app import config
from app.domutils import extract_from_cta

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

    from app.models import Deal
    if not title:
        return None
    return Deal(title=title.strip(), price=(price or 0.0), bottle_size_ml=size_ml, url=config.LASTBOTTLE_URL)