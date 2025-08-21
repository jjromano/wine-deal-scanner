"""Deal watching functionality with Playwright browser automation."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from playwright.async_api import Browser, BrowserContext, Page, Response, async_playwright

from . import config, extract
from .models import Deal

logger = structlog.get_logger(__name__)

# TODO: Update this selector based on actual LastBottle DOM structure
DEAL_ROOT_SELECTOR = "#deal-root"

# Deduplication window in seconds
DEDUP_WINDOW_SECONDS = 5 * 60  # 5 minutes


class DealWatcher:
    """Watches for new deals using browser automation."""

    def __init__(self) -> None:
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.seen_deals: dict[str, float] = {}
        self.running = False

    async def __aenter__(self) -> "DealWatcher":
        """Async context manager entry."""
        await self._setup_browser()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._cleanup_browser()

    async def _setup_browser(self) -> None:
        """Initialize browser, context, and page."""
        try:
            playwright = await async_playwright().start()
            
            # Launch headless Chromium browser
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                ]
            )
            
            # Create persistent context
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            
            # Create page
            self.page = await self.context.new_page()
            
            logger.info("Browser setup completed successfully")
            
        except Exception as e:
            await self._cleanup_browser()
            logger.error("Failed to setup browser", error=str(e))
            raise

    async def _cleanup_browser(self) -> None:
        """Clean up browser resources."""
        self.running = False
        
        if self.page:
            try:
                await asyncio.wait_for(self.page.close(), timeout=5.0)
            except Exception:
                pass
            self.page = None
            
        if self.context:
            try:
                await asyncio.wait_for(self.context.close(), timeout=5.0)
            except Exception:
                pass
            self.context = None
            
        if self.browser:
            try:
                await asyncio.wait_for(self.browser.close(), timeout=5.0)
            except Exception:
                pass
            self.browser = None
            
        logger.info("Browser cleanup completed")

    def _is_deal_response(self, response: Response) -> bool:
        """Check if response might contain deal data."""
        try:
            content_type = response.headers.get("content-type", "").lower()
            if "json" not in content_type:
                return False
                
            url = response.url.lower()
            deal_indicators = ["deal", "product", "api", "graphql"]
            
            return any(indicator in url for indicator in deal_indicators)
            
        except Exception:
            return False

    async def _handle_network_response(
        self, 
        response: Response, 
        on_new_deal: Callable[[Deal], Awaitable[None]]
    ) -> None:
        """Handle network response that might contain deal data."""
        try:
            if not self._is_deal_response(response):
                return
                
            if response.status != 200:
                return
                
            # Get JSON with timeout
            async with asyncio.timeout(3.0):
                response_data = await response.json()
                
            # Try to extract deal
            deal = extract.extract_deal_from_json(response_data)
            if deal:
                await self._safe_on_new_deal(deal, source="network", on_new_deal=on_new_deal)
                
        except Exception as e:
            logger.debug(
                "Failed to handle network response", 
                url=response.url, 
                error=str(e)
            )

    async def _setup_dom_observer(
        self, on_new_deal: Callable[[Deal], Awaitable[None]]
    ) -> None:
        """Setup DOM MutationObserver for deal detection."""
        if not self.page:
            return
            
        observer_script = f"""
        (function() {{
            let debounceTimer = null;
            let lastDealData = null;
            
            function debounce(func, delay) {{
                return function(...args) {{
                    clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(() => func.apply(this, args), delay);
                }};
            }}
            
            function checkForDeals() {{
                // Signal that deals should be checked
                window.dealCheckRequested = true;
                window.dealCheckTimestamp = Date.now();
            }}
            
            const debouncedCheck = debounce(checkForDeals, 400);
            
            // Setup MutationObserver
            const observer = new MutationObserver(function(mutations) {{
                let shouldCheck = false;
                
                mutations.forEach(function(mutation) {{
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {{
                        // Check if any added nodes or their descendants might be deals
                        mutation.addedNodes.forEach(function(node) {{
                            if (node.nodeType === Node.ELEMENT_NODE) {{
                                const element = node;
                                // Look for deal-related content
                                const text = element.textContent || '';
                                const hasPrice = /\$[0-9]+/.test(text);
                                const hasWineTerms = /wine|bottle|vintage|ml|oz/i.test(text);
                                
                                if (hasPrice && hasWineTerms) {{
                                    shouldCheck = true;
                                }}
                            }}
                        }});
                    }}
                }});
                
                if (shouldCheck) {{
                    debouncedCheck();
                }}
            }});
            
            // Observe deal root container
            const dealRoot = document.querySelector('{DEAL_ROOT_SELECTOR}') || document.body;
            observer.observe(dealRoot, {{
                childList: true,
                subtree: true,
                attributes: false
            }});
            
            // Initialize flags
            window.dealCheckRequested = false;
            window.dealCheckTimestamp = 0;
            
            console.log('Deal MutationObserver initialized');
        }})();
        """
        
        try:
            await self.page.add_init_script(observer_script)
            logger.debug("DOM observer setup completed")
        except Exception as e:
            logger.warning("Failed to setup DOM observer", error=str(e))

    async def _check_dom_for_deals(
        self, on_new_deal: Callable[[Deal], Awaitable[None]]
    ) -> None:
        """Check DOM for new deals if mutation was detected."""
        if not self.page:
            return
            
        try:
            # Check if deal check was requested
            async with asyncio.timeout(1.0):
                check_requested = await self.page.evaluate("window.dealCheckRequested")
                
            if not check_requested:
                return
                
            # Reset flag
            await self.page.evaluate("window.dealCheckRequested = false")
            
            # Extract deal from current DOM
            deal = await extract.extract_deal_from_dom(self.page)
            if deal:
                await self._safe_on_new_deal(deal, source="dom", on_new_deal=on_new_deal)
                
        except Exception as e:
            logger.debug("Failed to check DOM for deals", error=str(e))

    async def _safe_on_new_deal(
        self,
        deal: Deal,
        source: str,
        on_new_deal: Callable[[Deal], Awaitable[None]]
    ) -> None:
        """Safely handle new deal with deduplication and logging."""
        try:
            # Build deduplication key
            key = extract.deal_key(deal.title, deal.vintage, deal.price or 0.0)
            current_time = time.time()
            
            # Check for duplicates within window
            if key in self.seen_deals:
                last_seen = self.seen_deals[key]
                if current_time - last_seen < DEDUP_WINDOW_SECONDS:
                    logger.debug(
                        "Ignoring duplicate deal within dedup window",
                        key=key,
                        source=source,
                        seconds_ago=current_time - last_seen
                    )
                    return
            
            # Record this deal
            self.seen_deals[key] = current_time
            
            # Clean up old entries (keep last 100 to prevent memory growth)
            if len(self.seen_deals) > 100:
                # Remove entries older than 2x the dedup window
                cutoff = current_time - (2 * DEDUP_WINDOW_SECONDS)
                self.seen_deals = {
                    k: v for k, v in self.seen_deals.items() 
                    if v > cutoff
                }
            
            # Log deal discovery
            logger.info(
                "New deal discovered",
                source=source,
                title=deal.title,
                price=deal.price,
                vintage=deal.vintage,
                bottle_size_ml=deal.bottle_size_ml,
                url=deal.url,
                timestamp_ms=int(time.time() * 1000)
            )
            
            # Call the callback with timeout
            async with asyncio.timeout(10.0):
                await on_new_deal(deal)
                
        except Exception as e:
            logger.error(
                "Error in safe_on_new_deal",
                error=str(e),
                source=source,
                deal_title=getattr(deal, 'title', 'unknown')
            )

    async def watch(self, on_new_deal: Callable[[Deal], Awaitable[None]]) -> None:
        """Start watching for deals."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
            
        self.running = True
        
        try:
            # Setup network response handler
            async def response_handler(response: Response) -> None:
                if self.running:
                    await self._handle_network_response(response, on_new_deal)
            
            self.page.on("response", response_handler)
            
            # Setup DOM observer
            await self._setup_dom_observer(on_new_deal)
            
            # Navigate to LastBottle
            logger.info("Navigating to LastBottle", url=config.LASTBOTTLE_URL)
            async with asyncio.timeout(30.0):
                await self.page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")
            
            logger.info("Started watching for deals")
            
            # Main watching loop
            while self.running:
                try:
                    # Check DOM for deals periodically
                    await self._check_dom_for_deals(on_new_deal)
                    
                    # Small delay to prevent excessive CPU usage
                    await asyncio.sleep(1.0)
                    
                except asyncio.CancelledError:
                    logger.info("Deal watching cancelled")
                    break
                except Exception as e:
                    logger.warning("Error in watching loop", error=str(e))
                    await asyncio.sleep(5.0)  # Longer delay on error
                    
        except Exception as e:
            logger.error("Fatal error in watch loop", error=str(e))
            raise
        finally:
            # Clean up event listener
            if self.page:
                try:
                    self.page.remove_listener("response", response_handler)
                except Exception:
                    pass
            logger.info("Stopped watching for deals")


async def watch_deals(on_new_deal: Callable[[Deal], Awaitable[None]]) -> None:
    """
    Watch for new deals on LastBottle website.
    
    Args:
        on_new_deal: Async callback function to call when a new deal is found
    """
    async with DealWatcher() as watcher:
        await watcher.watch(on_new_deal)