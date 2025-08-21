"""Main application entry point for the wine deal scanner."""

import asyncio
import signal
import sys
from datetime import datetime, timedelta

import structlog

from .config import DEAL_DEDUP_MINUTES
from .extract import deal_key
from .models import Deal, VivinoData
from .notify import telegram_send
from .vivino import quick_lookup
from . import watcher

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class DealDeduplicator:
    """Handles deal deduplication with time-based expiry."""

    def __init__(self, dedup_minutes: int = DEAL_DEDUP_MINUTES) -> None:
        self.dedup_minutes = dedup_minutes
        self.seen_deals: dict[str, datetime] = {}

    def is_duplicate(self, deal: Deal) -> bool:
        """
        Check if a deal is a duplicate within the dedup window.

        Args:
            deal: Deal to check

        Returns:
            True if deal is a duplicate, False otherwise
        """
        key = deal_key(deal.title, deal.vintage, deal.price)
        now = datetime.now()

        # Clean up expired entries
        cutoff = now - timedelta(minutes=self.dedup_minutes)
        expired_keys = [k for k, timestamp in self.seen_deals.items() if timestamp < cutoff]
        for k in expired_keys:
            del self.seen_deals[k]

        # Check if deal is duplicate
        if key in self.seen_deals:
            return True

        # Record this deal
        self.seen_deals[key] = now
        return False


class WineDealScanner:
    """Main application class for the wine deal scanner."""

    def __init__(self) -> None:
        self.deduplicator = DealDeduplicator()
        self.running = False
        self._stop_event = asyncio.Event()

    async def process_deal(self, deal: Deal) -> None:
        """
        Process a discovered deal: enrich with Vivino data and send notification.

        Args:
            deal: Deal to process
        """
        logger.info("Processing new deal", deal=str(deal))

        # Check for duplicates
        if self.deduplicator.is_duplicate(deal):
            logger.info("Skipping duplicate deal", deal=str(deal))
            return

        # Enrich with Vivino data (with strict timeout)
        vivino_data = None
        try:
            rating, rating_count, avg_price = await quick_lookup(
                deal.title,
                deal.vintage
            )

            if rating is not None or rating_count is not None or avg_price is not None:
                vivino_data = VivinoData(
                    rating=rating,
                    rating_count=rating_count,
                    avg_price=avg_price
                )
                logger.info("Enriched deal with Vivino data", vivino=str(vivino_data))
            else:
                logger.info("No Vivino data found for deal")

        except Exception as e:
            logger.warning("Failed to enrich deal with Vivino data", error=str(e))

        # Send Telegram notification
        try:
            success = await telegram_send(deal, vivino_data)
            if success:
                logger.info("Successfully sent Telegram notification")
            else:
                logger.error("Failed to send Telegram notification")
        except Exception as e:
            logger.error("Error sending Telegram notification", error=str(e))

    async def run(self) -> None:
        """Main application loop."""
        logger.info("Starting wine deal scanner")
        self.running = True

        try:
            # Create watcher coroutine and stop event task
            watch_task = asyncio.create_task(watcher.watch_deals(self.process_deal))
            stop_task = asyncio.create_task(self._stop_event.wait())
            
            # Wait for either the watcher to complete or stop signal
            done, pending = await asyncio.wait(
                [watch_task, stop_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error("Fatal error in main loop", error=str(e))
            raise
        finally:
            logger.info("Wine deal scanner stopped")

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Initiating graceful shutdown")
        self.running = False
        self._stop_event.set()


async def main() -> None:
    """Main entry point."""
    # Set up signal handlers for graceful shutdown
    scanner = WineDealScanner()

    def signal_handler() -> None:
        logger.info("Received shutdown signal")
        asyncio.create_task(scanner.shutdown())

    # Set up signal handlers
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

    try:
        await scanner.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await scanner.shutdown()
    except Exception as e:
        logger.error("Unhandled exception in main", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
