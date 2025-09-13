import re
from urllib.parse import quote
from app import config

# ALWAYS return (rating, count, avg_price, url) – allow None
async def lookup(page, query: str):
    url = f"https://www.vivino.com/search/wines?q={quote(query)}"
    if config.DEBUG: print("[vivino.debug] goto", url)
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector('[data-cy*="searchPage"], [data-testid*="search-page"]', timeout=4000)
    except:
        pass

    text = await page.evaluate("""
      () => {
        const card = document.querySelector('[data-cy*="searchPage"] [data-cy*="wineCard"]')
                  || document.querySelector('[data-testid*="wine-card"]')
                  || document.querySelector('[class*="WineCard"]');
        return card ? card.innerText : document.body.innerText;
      }
    """)

    rating = None
    m = re.search(r'\b(\d\.\d)\b\s*(?:★|stars?)', text, re.I)
    if not m:
        m = re.search(r'Rating\s*(\d\.\d)', text, re.I)
    if m:
        try: rating = float(m.group(1))
        except: pass

    count = None
    m = re.search(r'(\d{1,3}(?:,\d{3})*)\s+ratings?', text, re.I)
    if m:
        try: count = int(m.group(1).replace(',', ''))
        except: pass

    avg_price = None
    m = re.search(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', text)
    if m:
        try: avg_price = float(m.group(1).replace(',', ''))
        except: pass

    # Try to grab first card link
    link = None
    try:
        link = await page.eval_on_selector('[data-cy*="wineCard"] a, [data-testid*="wine-card"] a', 'el => el.href')
        if not isinstance(link, str) or 'vivino.com' not in link:
            link = None
    except:
        pass

    if config.DEBUG:
        print(f"[vivino.debug] result rating={rating} count={count} avg_price={avg_price} url={link}")

    return (rating, count, avg_price, link)

