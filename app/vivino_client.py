# Helper to run both vintage and overall lookups with the same UA/context
from app import config
from app import vivino

async def fetch_vivino_info(browser, title: str, existing_page=None):
    # Check if this is a non-vintage wine
    is_non_vintage = ' NV' in title or ' Non-Vintage' in title or ' non-vintage' in title
    
    # Extract vintage year from title (only if not NV)
    import re
    import random
    import asyncio
    
    vintage_year = None
    if not is_non_vintage:
        year_match = re.search(r'\b(19|20)\d{2}\b', title)
        vintage_year = year_match.group(0) if year_match else None
    
    # Create queries
    with_vintage_query = title  # Full title with vintage
    without_vintage_query = re.sub(r'\b(19|20)\d{2}\b','', title).strip() if vintage_year else title
    
    if config.DEBUG and is_non_vintage:
        print(f"[vivino_client] Non-vintage wine detected: {title}")
        print(f"[vivino_client] Skipping vintage-specific search")

    # Use existing page if provided, otherwise create new context and page
    if existing_page:
        page = existing_page
        should_close_ctx = False
    else:
        # Create context with enhanced stealth settings
        ctx = await browser.new_context(
            user_agent=config.USER_AGENT,
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},  # NYC
            permissions=["geolocation"],
            viewport={"width": 1366, "height": 768},  # Common desktop resolution
            screen={"width": 1366, "height": 768},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            color_scheme="light",
            reduced_motion="no-preference",
            forced_colors="none",
            extra_http_headers={
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"'
            }
        )
        
        # Add stealth scripts
        await ctx.add_init_script("""
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
        """)
        
        page = await ctx.new_page()
        should_close_ctx = True
    
    # Add random delay between requests
    await asyncio.sleep(random.uniform(2.0, 5.0))
    
    # Search WITHOUT vintage first - this gives us OVERALL data (all vintages)
    # For NV wines, this is the only search we need to do
    overall_result = None
    if without_vintage_query != with_vintage_query or is_non_vintage:
        try:
            overall_result = await vivino.lookup(page, without_vintage_query)
            if config.DEBUG:
                print(f"[vivino_client] Overall search (no vintage): {overall_result}")
            
            # If we didn't get good overall data, try an even simpler search
            if not overall_result or not overall_result[0]:
                # Try with just the first 2-3 words (producer name)
                simple_query = ' '.join(without_vintage_query.split()[:3])
                if simple_query != without_vintage_query:
                    if config.DEBUG:
                        print(f"[vivino_client] Trying simplified search: {simple_query}")
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    simple_result = await vivino.lookup(page, simple_query)
                    if simple_result and simple_result[0]:
                        overall_result = simple_result
                        if config.DEBUG:
                            print(f"[vivino_client] Simplified search result: {simple_result}")
                            
        except Exception as e:
            if config.DEBUG: print(f"[vivino_client] Overall search failed: {e}")
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
                print(f"[vivino_client] Vintage search (with {vintage_year}): {vintage_result}")
        except Exception as e:
            if config.DEBUG: print(f"[vivino_client] Vintage search failed: {e}")
            vintage_result = None
    elif is_non_vintage:
        if config.DEBUG:
            print(f"[vivino_client] Skipping vintage search for non-vintage wine")
    
    # Only close context if we created it
    if should_close_ctx:
        await ctx.close()
    
    # Return (vintage_data, overall_data, vintage_year)
    return (vintage_result, overall_result, vintage_year)



