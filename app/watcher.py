import asyncio
import random
import re
from playwright.async_api import async_playwright
from app import config
from app.notify import telegram_send
from app.models import Deal
from app.domutils import extract_from_cta
from app.keep_awake import start_keep_awake, stop_keep_awake

def _deal_id(title: str) -> str:
    """Create a simple deal ID from the title"""
    return (title or "").strip().lower()

async def enhanced_vivino_lookup(browser, query: str):
    """Enhanced Vivino lookup with advanced anti-detection"""
    try:
        # Create a new context specifically for Vivino with enhanced stealth
        vivino_ctx = await browser.new_context(
            user_agent=config.USER_AGENT, 
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        
        # Add stealth scripts to Vivino context
        await vivino_ctx.add_init_script("""
            // Override webdriver detection
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', { 
                get: () => ['en-US', 'en'] 
            });
            
            // Override chrome runtime
            window.chrome = {
                runtime: {}
            };
        """)
        
        page = await vivino_ctx.new_page()
        
        # Add random delay
        await asyncio.sleep(random.uniform(2.0, 4.0))
        
        # Navigate to Vivino search
        url = f"https://www.vivino.com/search/wines?q={query.replace(' ', '%20')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Human-like behavior
        await page.mouse.move(random.randint(100, 500), random.randint(100, 400))
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # Wait for content with multiple fallbacks
        try:
            await page.wait_for_selector('[data-cy*="searchPage"], [data-testid*="search-page"], .wine-card, [class*="WineCard"]', timeout=10000)
        except:
            # If main selectors fail, try to wait for any content
            await asyncio.sleep(2.0)
        
        # Extract data with multiple strategies
        data = await page.evaluate("""
            () => {
                // Strategy 1: Look for wine cards
                const cards = document.querySelectorAll('[data-cy*="wineCard"], [data-testid*="wine-card"], .wine-card, [class*="WineCard"]');
                if (cards.length > 0) {
                    const card = cards[0];
                    const text = card.innerText || '';
                    
                    // Extract rating
                    const ratingMatch = text.match(/\\b(\\d\\.\\d)\\b/);
                    const rating = ratingMatch ? parseFloat(ratingMatch[1]) : null;
                    
                    // Extract review count
                    const reviewMatch = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s+ratings?/i);
                    const reviewCount = reviewMatch ? parseInt(reviewMatch[1].replace(',', '')) : null;
                    
                    // Extract average price
                    const priceMatch = text.match(/\\$\\s*(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)/);
                    const avgPrice = priceMatch ? parseFloat(priceMatch[1].replace(',', '')) : null;
                    
                    // Extract link
                    const linkEl = card.querySelector('a[href*="/wines/"], a[href*="/w/"]');
                    const link = linkEl ? linkEl.href : null;
                    
                    return { rating, reviewCount, avgPrice, link };
                }
                
                // Strategy 2: Look for any wine-related content
                const bodyText = document.body.innerText || '';
                const ratingMatch = bodyText.match(/\\b(\\d\\.\\d)\\b/);
                const rating = ratingMatch ? parseFloat(ratingMatch[1]) : null;
                
                const reviewMatch = bodyText.match(/(\\d{1,3}(?:,\\d{3})*)\\s+ratings?/i);
                const reviewCount = reviewMatch ? parseInt(reviewMatch[1].replace(',', '')) : null;
                
                const priceMatch = bodyText.match(/\\$\\s*(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)/);
                const avgPrice = priceMatch ? parseFloat(priceMatch[1].replace(',', '')) : null;
                
                return { rating, reviewCount, avgPrice, link: null };
            }
        """)
        
        # Clean up the link if we got one
        link = data.get('link')
        if link and isinstance(link, str) and 'vivino.com' in link:
            # Remove unwanted parameters
            from urllib.parse import urlparse, parse_qs, urlunparse
            try:
                parsed = urlparse(link)
                query_params = parse_qs(parsed.query)
                query_params.pop('year', None)
                query_params.pop('price_id', None)
                
                clean_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items() if v])
                clean_parsed = parsed._replace(query=clean_query)
                link = urlunparse(clean_parsed)
            except:
                pass
        
        return (data.get('rating'), data.get('reviewCount'), data.get('avgPrice'), link)
        
    except Exception as e:
        if config.DEBUG:
            print(f"[vivino] lookup error: {e}")
        return (None, None, None, None)
    finally:
        # Always close the Vivino context
        try:
            await vivino_ctx.close()
        except:
            pass

async def run_enhanced_watcher():
    """Enhanced watcher with working deal detection + improved Vivino lookups"""
    print(f"[enhanced] Starting enhanced watcher - DEBUG={config.DEBUG}")
    
    # Start keeping computer awake
    await start_keep_awake()
    
    # Start playwright
    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(headless=not config.HEADFUL)
        # Use the same simple context as minimal version for LastBottle
        ctx = await browser.new_context(user_agent=config.USER_AGENT, locale="en-US")
        
        page = await ctx.new_page()
        
        print("[enhanced] Navigating to LastBottle...")
        await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")
        
        # Track the last deal we saw
        last_deal_id = None
        notification_count = 0
        
        print("[enhanced] Starting deal monitoring loop...")
        
        while True:
            try:
                # Wait a bit between checks - use same timing as minimal
                await asyncio.sleep(2.0 + random.random() * 1.0)
                
                # Refresh the page to get the latest deal
                if config.DEBUG:
                    print("[enhanced] Refreshing page to check for new deals...")
                await page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(1.0)  # Give it a moment to fully load
                
                # Extract current deal info using the working extraction logic
                title, price = await extract_from_cta(page)
                
                if config.DEBUG:
                    print(f"[enhanced] Current: title='{title}' price={price}")
                
                # Skip if no title or generic title
                if not title or config.is_generic_title(title):
                    if config.DEBUG and title:
                        print(f"[enhanced] Skipping generic title: {title}")
                    continue
                
                # Skip if price is too low (likely invalid)
                if price is not None and price < 5.0:
                    if config.DEBUG:
                        print(f"[enhanced] Skipping low price: {price}")
                    price = None
                
                # Create deal ID
                current_deal_id = _deal_id(title)
                
                if config.DEBUG:
                    print(f"[enhanced] Deal ID: current='{current_deal_id}' last='{last_deal_id}'")
                
                # Check if this is a new deal
                if current_deal_id and current_deal_id != last_deal_id:
                    print(f"[enhanced] 🎉 NEW DEAL DETECTED!")
                    print(f"[enhanced] Title: {title}")
                    print(f"[enhanced] Price: ${price:.2f}" if price else "[enhanced] Price: Unknown")
                    
                    # Create deal object - ensure price is valid for Pydantic
                    deal_price = price if price and price > 0 else 1.0  # Use 1.0 as fallback to satisfy gt=0
                    deal = Deal(
                        title=title.strip(),
                        price=deal_price,
                        bottle_size_ml=750,
                        url=config.LASTBOTTLE_URL
                    )
                    
                    # Try to get Vivino data
                    vivino_data = None
                    try:
                        print("[enhanced] Looking up Vivino data...")
                        
                        # Check if this is a non-vintage wine
                        is_non_vintage = ' NV' in title or ' Non-Vintage' in title or ' non-vintage' in title
                        
                        # Extract vintage year
                        vintage_year = None
                        if not is_non_vintage:
                            year_match = re.search(r'\b(19|20)\d{2}\b', title)
                            vintage_year = year_match.group(0) if year_match else None
                        
                        # Create queries
                        with_vintage_query = title
                        without_vintage_query = re.sub(r'\b(19|20)\d{2}\b','', title).strip() if vintage_year else title
                        
                        # Search for overall data (without vintage)
                        overall_result = None
                        if without_vintage_query != with_vintage_query or is_non_vintage:
                            overall_result = await enhanced_vivino_lookup(browser, without_vintage_query)
                            if config.DEBUG:
                                print(f"[enhanced] Overall search result: {overall_result}")
                        
                        # Search for vintage-specific data (with vintage)
                        vintage_result = None
                        if with_vintage_query and not is_non_vintage:
                            await asyncio.sleep(random.uniform(3.0, 5.0))  # Delay between searches
                            vintage_result = await enhanced_vivino_lookup(browser, with_vintage_query)
                            if config.DEBUG:
                                print(f"[enhanced] Vintage search result: {vintage_result}")
                        
                        vivino_data = (vintage_result, overall_result, vintage_year)
                        
                    except Exception as e:
                        if config.DEBUG:
                            print(f"[enhanced] Vivino lookup failed: {e}")
                        vivino_data = None
                    
                    # Send notification
                    try:
                        print("[enhanced] Sending Telegram notification...")
                        await telegram_send(deal, vivino_data)
                        notification_count += 1
                        print(f"[enhanced] ✅ Notification sent! (Total: {notification_count})")
                    except Exception as e:
                        print(f"[enhanced] ❌ Failed to send notification: {e}")
                        # Try sending without Vivino data as fallback
                        try:
                            print("[enhanced] Trying fallback notification without Vivino data...")
                            await telegram_send(deal, None)
                            notification_count += 1
                            print(f"[enhanced] ✅ Fallback notification sent! (Total: {notification_count})")
                        except Exception as e2:
                            print(f"[enhanced] ❌ Fallback notification also failed: {e2}")
                    
                    # Update last deal
                    last_deal_id = current_deal_id
                else:
                    if config.DEBUG:
                        print("[enhanced] Same deal, no notification needed")
                
            except Exception as e:
                print(f"[enhanced] ❌ Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                # Continue the loop even if there's an error
                continue
                
    finally:
        # Stop keeping computer awake
        await stop_keep_awake()
        
        # Clean up
        try:
            await browser.close()
        except:
            pass
        try:
            await p.stop()
        except:
            pass
