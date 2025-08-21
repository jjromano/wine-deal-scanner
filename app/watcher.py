"""Deal watching functionality with Playwright browser automation."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    Route,
    async_playwright,
)

from . import config, extract
from .enrichment import enrich_deal
from .models import Deal, DealDetails
from .notify import send_telegram_message

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
        self.blocked_requests_count = 0
        self.last_deal_key: str | None = None
        self.last_heartbeat = time.time()
        self.last_dom_check_time = 0.0
        self.debounce_delay = 0.4  # 400ms debounce

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
                user_agent=config.USER_AGENT,
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )

            # Create page
            self.page = await self.context.new_page()

            # Setup request blocking in safe mode
            if config.SAFE_MODE:
                await self._setup_request_blocking()

            logger.info(
                "Browser setup completed successfully",
                safe_mode=config.SAFE_MODE,
                user_agent=config.USER_AGENT
            )

        except Exception as e:
            await self._cleanup_browser()
            logger.error("Failed to setup browser", error=str(e))
            raise

    async def _setup_request_blocking(self) -> None:
        """Setup request blocking for safe mode."""
        if not self.page:
            return

        # Common analytics and tracking domains to block
        blocked_domains = {
            "google-analytics.com",
            "googletagmanager.com",
            "facebook.com",
            "facebook.net",
            "doubleclick.net",
            "googlesyndication.com",
            "googleadservices.com",
            "adsystem.amazon.com",
            "amazon-adsystem.com",
            "scorecardresearch.com",
            "quantserve.com",
            "outbrain.com",
            "taboola.com",
            "bing.com",
            "hotjar.com",
            "fullstory.com",
            "segment.com",
            "mixpanel.com",
            "amplitude.com",
        }

        async def request_handler(route: Route) -> None:
            request = route.request
            url = request.url.lower()
            resource_type = request.resource_type

            # Block images, media, fonts
            if resource_type in {"image", "media", "font"}:
                self.blocked_requests_count += 1
                await route.abort()
                return

            # Block analytics domains
            for domain in blocked_domains:
                if domain in url:
                    self.blocked_requests_count += 1
                    await route.abort()
                    return

            # Allow XHR, JSON, HTML, CSS, and scripts
            if resource_type in {"xhr", "fetch", "document", "stylesheet", "script"}:
                await route.continue_()
                return

            # Block everything else by default in safe mode
            self.blocked_requests_count += 1
            await route.abort()

        await self.page.route("**/*", request_handler)
        logger.debug("Request blocking setup completed for safe mode")

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

            # Try to extract deal using legacy method for JSON
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

        observer_script = rf"""
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

            # Implement debouncing on Python side
            current_time = time.time()
            if current_time - self.last_dom_check_time < self.debounce_delay:
                return  # Skip if within debounce window

            # Reset flag and update last check time
            await self.page.evaluate("window.dealCheckRequested = false")
            self.last_dom_check_time = current_time

            # Try both extraction methods
            # First try new HTML extraction
            try:
                html_content = await self.page.content()
                deal_details = extract.extract_deal_details(html_content)
                if deal_details:
                    await self._process_deal_details(deal_details, source="dom")
                    return
            except Exception as e:
                logger.debug("HTML extraction failed, trying legacy DOM extraction", error=str(e))

            # Fallback to legacy DOM extraction
            deal = await extract.extract_deal_from_dom(self.page)
            if deal:
                await self._safe_on_new_deal(deal, source="dom", on_new_deal=on_new_deal)

        except Exception as e:
            logger.debug("Failed to check DOM for deals", error=str(e))

    async def _process_deal_details(
        self,
        deal_details: DealDetails,
        source: str
    ) -> None:
        """Process deal details through enrichment and notification pipeline."""
        try:
            # Build deduplication key
            key = extract.deal_key(deal_details.wine_name, str(deal_details.vintage) if deal_details.vintage else None, deal_details.deal_price)
            current_time = time.time()

            # Update last deal key for heartbeat logging
            self.last_deal_key = key

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
                wine_name=deal_details.wine_name,
                vintage=deal_details.vintage,
                deal_price=deal_details.deal_price,
                bottle_size_ml=deal_details.bottle_size_ml,
                timestamp_ms=int(time.time() * 1000)
            )

            # Enrich deal with Vivino data
            try:
                logger.debug("Starting deal enrichment", wine_name=deal_details.wine_name)
                async with asyncio.timeout(15.0):  # Allow time for Vivino lookup
                    enriched_deal = await enrich_deal(deal_details)

                logger.info(
                    "Deal enrichment completed",
                    wine_name=deal_details.wine_name,
                    has_vivino_data=enriched_deal.has_vivino_data,
                    best_rating=enriched_deal.best_rating
                )

            except Exception as e:
                logger.warning(
                    "Deal enrichment failed, proceeding with basic deal info",
                    wine_name=deal_details.wine_name,
                    error=str(e)
                )
                # Create enriched deal with just the basic info (no Vivino data)
                from .models import EnrichedDeal
                enriched_deal = EnrichedDeal(
                    wine_name=deal_details.wine_name,
                    vintage=deal_details.vintage,
                    bottle_size_ml=deal_details.bottle_size_ml,
                    deal_price=deal_details.deal_price
                )

            # Send Telegram notification
            try:
                logger.debug("Sending Telegram notification", wine_name=deal_details.wine_name)
                async with asyncio.timeout(15.0):
                    success = await send_telegram_message(enriched_deal)

                if success:
                    logger.info(
                        "Deal notification sent successfully",
                        wine_name=deal_details.wine_name,
                        vintage=deal_details.vintage,
                        source=source
                    )
                else:
                    logger.error(
                        "Failed to send deal notification",
                        wine_name=deal_details.wine_name,
                        vintage=deal_details.vintage,
                        source=source
                    )

            except Exception as e:
                logger.error(
                    "Error sending Telegram notification",
                    wine_name=deal_details.wine_name,
                    error=str(e)
                )

        except Exception as e:
            logger.error(
                "Error in deal processing pipeline",
                error=str(e),
                source=source,
                wine_name=getattr(deal_details, 'wine_name', 'unknown')
            )

    async def _safe_on_new_deal(
        self,
        deal: Deal,
        source: str,
        on_new_deal: Callable[[Deal], Awaitable[None]]
    ) -> None:
        """Safely handle new deal with deduplication and logging (legacy support)."""
        try:
            # Convert old Deal to DealDetails for new pipeline
            deal_details = DealDetails(
                wine_name=deal.title,
                vintage=int(deal.vintage) if deal.vintage and deal.vintage.isdigit() else None,
                bottle_size_ml=deal.bottle_size_ml if hasattr(deal, 'bottle_size_ml') else 750,
                deal_price=deal.price or 0.0
            )

            # Process through new enrichment pipeline
            await self._process_deal_details(deal_details, source)

            # Also call the legacy callback for backwards compatibility
            try:
                async with asyncio.timeout(10.0):
                    await on_new_deal(deal)
            except Exception as e:
                logger.debug("Legacy callback failed", error=str(e))

        except Exception as e:
            logger.error(
                "Error in safe_on_new_deal",
                error=str(e),
                source=source,
                deal_title=getattr(deal, 'title', 'unknown')
            )

    async def _log_heartbeat(self) -> None:
        """Log periodic heartbeat with status information."""
        current_time = time.time()

        # Only log heartbeat every 60 seconds
        if current_time - self.last_heartbeat < 60.0:
            return

        self.last_heartbeat = current_time

        logger.info(
            "Heartbeat",
            mode="event",
            page_ready=self.page is not None and self.running,
            blocked_requests_count=self.blocked_requests_count,
            last_deal_key=self.last_deal_key,
            safe_mode=config.SAFE_MODE,
            seen_deals_count=len(self.seen_deals)
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

                    # Log heartbeat periodically
                    await self._log_heartbeat()

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
