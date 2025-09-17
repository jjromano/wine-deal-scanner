# Advanced stealth Vivino client with session persistence and human-like behavior
import asyncio
import random
import time
from playwright.async_api import async_playwright
from playwright_stealth import stealth
from app import config
from app import vivino

class VivinoStealthClient:
    def __init__(self):
        self.browser = None
        self.context = None
        self.session_warmed = False
        self.last_request_time = 0
        self.request_count = 0
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def start(self):
        """Initialize browser with advanced stealth settings"""
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=not config.HEADFUL,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # Faster loading
                '--disable-javascript',  # We'll enable it selectively
            ]
        )
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            user_agent=config.USER_AGENT,
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},
            permissions=["geolocation"],
            viewport={"width": 1366, "height": 768},
            screen={"width": 1366, "height": 768},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            color_scheme="light",
            reduced_motion="no-preference",
            forced_colors="none",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
        )
        
        # Apply stealth mode
        stealth_instance = stealth.Stealth()
        await stealth_instance.apply_stealth_async(self.context)
        
        # Add additional stealth scripts
        await self.context.add_init_script("""
            // Override webdriver detection
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Override automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
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
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Add realistic timing
            const originalDate = Date;
            Date = class extends originalDate {
                constructor(...args) {
                    if (args.length === 0) {
                        super(originalDate.now() + Math.random() * 100);
                    } else {
                        super(...args);
                    }
                }
            };
        """)
        
    async def close(self):
        """Clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
            
    async def warm_session(self):
        """Warm up the session by browsing Vivino naturally"""
        if self.session_warmed:
            return
            
        page = await self.context.new_page()
        
        try:
            if config.DEBUG:
                print("[stealth] Warming session...")
                
            # Visit Vivino homepage first
            await page.goto("https://www.vivino.com/", wait_until="domcontentloaded")
            await self._human_delay(2, 4)
            
            # Simulate human browsing behavior
            await self._simulate_human_behavior(page)
            
            # Visit a popular wine page
            await page.goto("https://www.vivino.com/en/caymus-vineyards-cabernet-sauvignon/w/66284", wait_until="domcontentloaded")
            await self._human_delay(3, 6)
            
            # Simulate more human behavior
            await self._simulate_human_behavior(page)
            
            self.session_warmed = True
            
            if config.DEBUG:
                print("[stealth] Session warmed successfully")
                
        except Exception as e:
            if config.DEBUG:
                print(f"[stealth] Session warming failed: {e}")
        finally:
            await page.close()
            
    async def _human_delay(self, min_seconds=1, max_seconds=3):
        """Add human-like delays"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        
    async def _simulate_human_behavior(self, page):
        """Simulate human-like browsing behavior"""
        try:
            # Random mouse movements
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 1200)
                y = random.randint(100, 600)
                await page.mouse.move(x, y)
                await self._human_delay(0.5, 1.5)
                
            # Random scrolling
            for _ in range(random.randint(1, 3)):
                scroll_amount = random.randint(200, 800)
                await page.mouse.wheel(0, scroll_amount)
                await self._human_delay(1, 2)
                
            # Random clicks (safe areas)
            try:
                # Click on safe elements like headers or navigation
                safe_selectors = ['header', 'nav', '.header', '.navigation']
                for selector in safe_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            await element.click()
                            await self._human_delay(0.5, 1)
                            break
                    except:
                        continue
            except:
                pass
                
        except Exception as e:
            if config.DEBUG:
                print(f"[stealth] Human behavior simulation failed: {e}")
                
    async def _rate_limit_check(self):
        """Implement smart rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Minimum delay between requests
        min_delay = 3.0
        
        # Increase delay based on request count
        if self.request_count > 5:
            min_delay = 10.0
        elif self.request_count > 10:
            min_delay = 30.0
            
        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            if config.DEBUG:
                print(f"[stealth] Rate limiting: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            
        self.last_request_time = time.time()
        self.request_count += 1
        
    async def lookup_with_retry(self, query: str, max_retries: int = 3):
        """Perform Vivino lookup with retry logic and session warming"""
        await self._rate_limit_check()
        
        # Warm session if not already done
        if not self.session_warmed:
            await self.warm_session()
            
        page = await self.context.new_page()
        
        for attempt in range(max_retries):
            try:
                if config.DEBUG:
                    print(f"[stealth] Attempt {attempt + 1}/{max_retries} for: {query}")
                    
                # Add human-like delay before request
                await self._human_delay(2, 5)
                
                # Perform the lookup
                result = await vivino.lookup(page, query)
                
                if result and result[0]:  # If we got a rating
                    if config.DEBUG:
                        print(f"[stealth] Success on attempt {attempt + 1}")
                    await page.close()
                    return result
                else:
                    if config.DEBUG:
                        print(f"[stealth] No data on attempt {attempt + 1}, retrying...")
                        
            except Exception as e:
                if config.DEBUG:
                    print(f"[stealth] Attempt {attempt + 1} failed: {e}")
                    
            # Wait before retry with exponential backoff
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * random.uniform(5, 10)
                if config.DEBUG:
                    print(f"[stealth] Waiting {wait_time:.1f}s before retry...")
                await asyncio.sleep(wait_time)
                
        await page.close()
        return (None, None, None, None)

# Convenience function for backward compatibility
async def fetch_vivino_info_stealth(browser, title: str):
    """Enhanced Vivino info fetching with stealth capabilities"""
    # Check if this is a non-vintage wine
    is_non_vintage = ' NV' in title or ' Non-Vintage' in title or ' non-vintage' in title
    
    # Extract vintage year from title (only if not NV)
    import re
    vintage_year = None
    if not is_non_vintage:
        year_match = re.search(r'\b(19|20)\d{2}\b', title)
        vintage_year = year_match.group(0) if year_match else None
    
    # Create queries
    with_vintage_query = title  # Full title with vintage
    without_vintage_query = re.sub(r'\b(19|20)\d{2}\b','', title).strip() if vintage_year else title
    
    if config.DEBUG and is_non_vintage:
        print(f"[stealth] Non-vintage wine detected: {title}")
        print(f"[stealth] Skipping vintage-specific search")
    
    # Use the existing browser instead of creating a new one
    # Create a new context with stealth settings
    ctx = await browser.new_context(
        user_agent=config.USER_AGENT,
        locale="en-US",
        timezone_id="America/New_York",
        geolocation={"longitude": -74.006, "latitude": 40.7128},
        permissions=["geolocation"],
        viewport={"width": 1366, "height": 768},
        screen={"width": 1366, "height": 768},
        device_scale_factor=1,
        is_mobile=False,
        has_touch=False,
        color_scheme="light",
        reduced_motion="no-preference",
        forced_colors="none",
        extra_http_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
    )
    
    # Apply stealth mode
    from playwright_stealth import stealth
    stealth_instance = stealth.Stealth()
    await stealth_instance.apply_stealth_async(ctx)
    
    page = await ctx.new_page()
    
    try:
        # Add random delay before starting
        await asyncio.sleep(random.uniform(2.0, 5.0))
        
        # Search WITHOUT vintage first - this gives us OVERALL data (all vintages)
        # For NV wines, this is the only search we need to do
        overall_result = None
        if without_vintage_query != with_vintage_query or is_non_vintage:
            try:
                overall_result = await vivino.lookup(page, without_vintage_query)
                if config.DEBUG:
                    print(f"[stealth] Overall search (no vintage): {overall_result}")
                
                # If we didn't get good overall data, try an even simpler search
                if not overall_result or not overall_result[0]:
                    # Try with just the first 2-3 words (producer name)
                    simple_query = ' '.join(without_vintage_query.split()[:3])
                    if simple_query != without_vintage_query:
                        if config.DEBUG:
                            print(f"[stealth] Trying simplified search: {simple_query}")
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                        simple_result = await vivino.lookup(page, simple_query)
                        if simple_result and simple_result[0]:
                            overall_result = simple_result
                            if config.DEBUG:
                                print(f"[stealth] Simplified search result: {simple_result}")
                                
            except Exception as e:
                if config.DEBUG: print(f"[stealth] Overall search failed: {e}")
                overall_result = None
        
        # Search WITH vintage - this gives us VINTAGE-SPECIFIC data
        # Skip this for non-vintage wines since they don't have vintage-specific data
        vintage_result = None
        if with_vintage_query and not is_non_vintage:
            try:
                # Add delay between searches
                if overall_result:
                    await asyncio.sleep(random.uniform(3.0, 6.0))
                vintage_result = await vivino.lookup(page, with_vintage_query)
                if config.DEBUG:
                    print(f"[stealth] Vintage search (with {vintage_year}): {vintage_result}")
            except Exception as e:
                if config.DEBUG: print(f"[stealth] Vintage search failed: {e}")
                vintage_result = None
        elif is_non_vintage:
            if config.DEBUG:
                print(f"[stealth] Skipping vintage search for non-vintage wine")
        
        # Return (vintage_data, overall_data, vintage_year)
        return (vintage_result, overall_result, vintage_year)
        
    finally:
        # Clean up the context
        await ctx.close()
