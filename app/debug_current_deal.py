#!/usr/bin/env python3
"""
Debug script to check what deal the app is currently detecting
"""

import asyncio
from playwright.async_api import async_playwright
from app import config
from app.watcher_minimal import extract_deal_info

async def debug_current_deal():
    print("🔍 DEBUGGING CURRENT DEAL DETECTION")
    print("=" * 50)
    
    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(headless=False)  # Show browser for visual inspection
        ctx = await browser.new_context(user_agent=config.USER_AGENT, locale="en-US")
        page = await ctx.new_page()
        
        print("🌐 Navigating to LastBottle...")
        await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")
        
        print("⏳ Waiting 3 seconds for page to fully load...")
        await asyncio.sleep(3)
        
        print("🔍 Extracting deal information...")
        title, price = await extract_deal_info(page)
        
        print("\n📊 RESULTS:")
        print(f"Title: '{title}'")
        print(f"Price: {price}")
        print(f"Deal ID: '{title.lower().strip() if title else 'NO TITLE'}'")
        
        print("\n🌐 Browser is still open - you can visually inspect the page")
        print("Press Ctrl+C to close...")
        
        # Keep browser open for visual inspection
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Closing browser...")
            
    finally:
        try:
            await browser.close()
        except:
            pass
        try:
            await p.stop()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(debug_current_deal())
