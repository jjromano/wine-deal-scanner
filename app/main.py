import sys, asyncio
from app.watcher import run_watcher
from app import config
from app.extract import extract_deal_from_dom
from playwright.async_api import async_playwright
from app.vivino_client import fetch_vivino_info
from app.notify import telegram_send

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--notify-once":
        return asyncio.run(_once())
    return asyncio.run(run_watcher())

async def _once():
    print(f"[once] flags DEBUG={config.DEBUG} SAFE_MODE={config.SAFE_MODE} HEADFUL={config.HEADFUL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not config.HEADFUL)
        ctx = await browser.new_context(user_agent=config.USER_AGENT, locale="en-US")
        page = await ctx.new_page()
        print("[once] goto", config.LASTBOTTLE_URL)
        await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector('h1, .product-title, .deal-title', timeout=15000)
        except:
            pass
        deal = await extract_deal_from_dom(page)
        if not deal:
            print("notify-once: no deal parsed")
            return 2
        vintage, overall, vintage_year = (None, None, None)
        try:
            vintage, overall, vintage_year = await fetch_vivino_info(browser, deal.title)
        except Exception as e:
            if config.DEBUG: print("[vivino.debug] error:", e)
        ok, status, body = await telegram_send(deal, (vintage, overall, vintage_year))
        print("notify-once:", ok, status, (body[:80] if isinstance(body,str) else body))
        await ctx.close()
        await browser.close()
        return 0

if __name__ == "__main__":
    sys.exit(main())