import asyncio
import random
import re
from playwright.async_api import async_playwright
from app import config
from app.notify import telegram_send
from app.models import Deal

def _deal_id(title: str) -> str:
    """Create a simple deal ID from the title"""
    return (title or "").strip().lower()

async def extract_deal_info(page):
    """Extract the current deal title and price from the page"""
    try:
        # Get the page title first
        title = await page.evaluate("""
            () => {
                // Try to find the wine title
                const selectors = [
                    '.product-title',
                    '.deal-title', 
                    'h1.product-title',
                    'h1.title',
                    'h1'
                ];
                
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (el && el.innerText && el.innerText.trim()) {
                        return el.innerText.trim();
                    }
                }
                
                // Fallback to document title
                return document.title || '';
            }
        """)
        
        # Get the price
        price_text = await page.evaluate("""
            () => {
                // Look for the "Last Bottle" price specifically
                const followRight = document.querySelector('.follow-right');
                if (followRight) {
                    const lastBottleHolder = followRight.querySelector('.price-holder');
                    if (lastBottleHolder && lastBottleHolder.innerText.toLowerCase().includes('last bottle')) {
                        const priceEl = lastBottleHolder.querySelector('div');
                        if (priceEl) {
                            const m = priceEl.innerText.match(/\\$\\s*\\d[\\d,]*(?:\\.\\d{2})?/);
                            if (m) return m[0];
                        }
                    }
                }
                
                // Fallback: look for any price
                const money = /\\$\\s*\\d[\\d,]*(?:\\.\\d{2})?/;
                const elements = document.querySelectorAll('*');
                for (const el of elements) {
                    const text = (el.innerText || '').toLowerCase();
                    if (text.includes('last bottle') && text.includes('$')) {
                        const m = text.match(money);
                        if (m) return m[0];
                    }
                }
                
                return null;
            }
        """)
        
        # Parse price
        price = None
        if price_text:
            m = re.search(r'\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)', price_text)
            if m:
                try:
                    price = float(m.group(1).replace(",", ""))
                except:
                    pass
        
        return title, price
        
    except Exception as e:
        if config.DEBUG:
            print(f"[extract] error: {e}")
        return "", None

async def run_minimal_watcher():
    """Minimal watcher that focuses only on deal detection and notification"""
    print(f"[minimal] Starting minimal watcher - DEBUG={config.DEBUG}")
    
    # Start playwright
    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(headless=not config.HEADFUL)
        ctx = await browser.new_context(user_agent=config.USER_AGENT, locale="en-US")
        page = await ctx.new_page()
        
        print("[minimal] Navigating to LastBottle...")
        await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")
        
        # Track the last deal we saw
        last_deal_id = None
        notification_count = 0
        
        print("[minimal] Starting deal monitoring loop...")
        
        while True:
            try:
                # Wait a bit between checks
                await asyncio.sleep(2.0 + random.random() * 1.0)
                
                # Refresh the page to get the latest deal
                if config.DEBUG:
                    print("[minimal] Refreshing page to check for new deals...")
                await page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(1.0)  # Give it a moment to fully load
                
                # Extract current deal info
                title, price = await extract_deal_info(page)
                
                if config.DEBUG:
                    print(f"[minimal] Current: title='{title}' price={price}")
                
                # Skip if no title or generic title
                if not title or config.is_generic_title(title):
                    if config.DEBUG and title:
                        print(f"[minimal] Skipping generic title: {title}")
                    continue
                
                # Skip if price is too low (likely invalid)
                if price is not None and price < 5.0:
                    if config.DEBUG:
                        print(f"[minimal] Skipping low price: {price}")
                    price = None
                
                # Create deal ID
                current_deal_id = _deal_id(title)
                
                if config.DEBUG:
                    print(f"[minimal] Deal ID: current='{current_deal_id}' last='{last_deal_id}'")
                
                # Check if this is a new deal
                if current_deal_id and current_deal_id != last_deal_id:
                    print(f"[minimal] 🎉 NEW DEAL DETECTED!")
                    print(f"[minimal] Title: {title}")
                    print(f"[minimal] Price: ${price:.2f}" if price else "[minimal] Price: Unknown")
                    
                    # Create deal object
                    deal = Deal(
                        title=title.strip(),
                        price=price or 0.0,
                        bottle_size_ml=750,
                        url=config.LASTBOTTLE_URL
                    )
                    
                    # Send notification (without Vivino for now to keep it simple)
                    try:
                        print("[minimal] Sending Telegram notification...")
                        await telegram_send(deal, None)  # No Vivino data for now
                        notification_count += 1
                        print(f"[minimal] ✅ Notification sent! (Total: {notification_count})")
                    except Exception as e:
                        print(f"[minimal] ❌ Failed to send notification: {e}")
                    
                    # Update last deal
                    last_deal_id = current_deal_id
                else:
                    if config.DEBUG:
                        print("[minimal] Same deal, no notification needed")
                
            except Exception as e:
                print(f"[minimal] ❌ Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                # Continue the loop even if there's an error
                continue
                
    finally:
        # Clean up
        try:
            await browser.close()
        except:
            pass
        try:
            await p.stop()
        except:
            pass
