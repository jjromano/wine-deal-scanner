"""Tests for watcher integration with enrichment and notifications."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.models import DealDetails, EnrichedDeal
from app.watcher import DealWatcher


class TestWatcherIntegration:
    """Tests for the integrated watcher functionality."""

    @pytest.mark.asyncio
    async def test_process_deal_details_complete_workflow(self) -> None:
        """Test complete deal processing workflow."""
        watcher = DealWatcher()

        deal_details = DealDetails(
            wine_name="Test Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=45.99
        )

        # Mock enriched deal
        enriched_deal = EnrichedDeal(
            wine_name="Test Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=45.99,
            overall_rating=4.2,
            overall_price=55.00,
            overall_reviews=1500
        )

        with patch('app.watcher.enrich_deal') as mock_enrich, \
             patch('app.watcher.send_telegram_message') as mock_telegram, \
             patch('app.watcher.extract.deal_key') as mock_key:

            mock_enrich.return_value = enriched_deal
            mock_telegram.return_value = True
            mock_key.return_value = "test_wine_2020_45.99"

            await watcher._process_deal_details(deal_details, "test")

            # Verify enrichment was called
            mock_enrich.assert_called_once_with(deal_details)

            # Verify Telegram notification was sent
            mock_telegram.assert_called_once_with(enriched_deal)

    @pytest.mark.asyncio
    async def test_process_deal_details_enrichment_failure(self) -> None:
        """Test deal processing when enrichment fails."""
        watcher = DealWatcher()

        deal_details = DealDetails(
            wine_name="Enrichment Fail Wine",
            vintage=2019,
            deal_price=35.00
        )

        with patch('app.watcher.enrich_deal') as mock_enrich, \
             patch('app.watcher.send_telegram_message') as mock_telegram, \
             patch('app.watcher.extract.deal_key') as mock_key:

            mock_enrich.side_effect = Exception("Vivino API error")
            mock_telegram.return_value = True
            mock_key.return_value = "enrichment_fail_wine_2019_35.0"

            await watcher._process_deal_details(deal_details, "test")

            # Should still send telegram with basic deal info
            mock_telegram.assert_called_once()

            # Check that EnrichedDeal was created with basic info only
            call_args = mock_telegram.call_args[0][0]
            assert call_args.wine_name == "Enrichment Fail Wine"
            assert call_args.vintage == 2019
            assert call_args.deal_price == 35.00
            assert not call_args.has_vivino_data

    @pytest.mark.asyncio
    async def test_process_deal_details_telegram_failure(self) -> None:
        """Test deal processing when Telegram notification fails."""
        watcher = DealWatcher()

        deal_details = DealDetails(
            wine_name="Telegram Fail Wine",
            deal_price=25.00
        )

        enriched_deal = EnrichedDeal(
            wine_name="Telegram Fail Wine",
            deal_price=25.00
        )

        with patch('app.watcher.enrich_deal') as mock_enrich, \
             patch('app.watcher.send_telegram_message') as mock_telegram, \
             patch('app.watcher.extract.deal_key') as mock_key:

            mock_enrich.return_value = enriched_deal
            mock_telegram.side_effect = Exception("Telegram API error")
            mock_key.return_value = "telegram_fail_wine_25.0"

            # Should not raise exception
            await watcher._process_deal_details(deal_details, "test")

            # Both should have been called
            mock_enrich.assert_called_once()
            mock_telegram.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_deal_details_deduplication(self) -> None:
        """Test deal deduplication logic."""
        watcher = DealWatcher()

        deal_details = DealDetails(
            wine_name="Duplicate Wine",
            vintage=2021,
            deal_price=40.00
        )

        with patch('app.watcher.enrich_deal') as mock_enrich, \
             patch('app.watcher.send_telegram_message') as mock_telegram, \
             patch('app.watcher.extract.deal_key') as mock_key, \
             patch('time.time') as mock_time:

            mock_key.return_value = "duplicate_wine_2021_40.0"
            mock_time.return_value = 1000.0

            # First call should process normally
            await watcher._process_deal_details(deal_details, "test")
            assert mock_enrich.call_count == 1
            assert mock_telegram.call_count == 1

            # Second call within dedup window should be ignored
            mock_time.return_value = 1200.0  # 200 seconds later (< 5 minutes)
            await watcher._process_deal_details(deal_details, "test")

            # Should not have been called again
            assert mock_enrich.call_count == 1
            assert mock_telegram.call_count == 1

            # Third call after dedup window should process
            mock_time.return_value = 1400.0  # 400 seconds later (> 5 minutes)
            await watcher._process_deal_details(deal_details, "test")

            # Should have been called again
            assert mock_enrich.call_count == 2
            assert mock_telegram.call_count == 2

    @pytest.mark.asyncio
    async def test_dom_extraction_with_html_method(self) -> None:
        """Test DOM extraction using new HTML method."""
        watcher = DealWatcher()

        # Mock page
        mock_page = AsyncMock()
        mock_page.evaluate.side_effect = [True, None]  # dealCheckRequested, reset
        mock_page.is_closed.return_value = False  # Page is not closed
        mock_page.content.return_value = """
        <html>
        <body>
            <h1>Test Wine 2020</h1>
            <div class="price">Deal Price: $45.99</div>
            <div class="size">750ml</div>
        </body>
        </html>
        """
        watcher.page = mock_page

        # Mock deal details extraction
        deal_details = DealDetails(
            wine_name="Test Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=45.99
        )

        with patch('app.watcher.extract.extract_deal_details') as mock_extract, \
             patch.object(watcher, '_process_deal_details') as mock_process:

            mock_extract.return_value = deal_details

            # Mock callback for legacy support
            mock_callback = AsyncMock()

            await watcher._check_dom_for_deals(mock_callback)

            # Should have used HTML extraction
            mock_extract.assert_called_once()
            mock_process.assert_called_once_with(deal_details, source="dom")

            # Should not have called legacy callback
            mock_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_dom_extraction_fallback_to_legacy(self) -> None:
        """Test DOM extraction fallback to legacy method."""
        watcher = DealWatcher()

        # Mock page
        mock_page = AsyncMock()
        mock_page.evaluate.side_effect = [True, None]  # dealCheckRequested, reset
        mock_page.is_closed.return_value = False  # Page is not closed
        mock_page.content.return_value = "<html><body>No deal content</body></html>"
        watcher.page = mock_page

        # Mock legacy deal
        from app.models import Deal
        legacy_deal = Deal(
            title="Legacy Wine",
            price=30.00,
            vintage="2019",
            region="Napa",
            url="http://example.com"
        )

        with patch('app.watcher.extract.extract_deal_details') as mock_html_extract, \
             patch('app.watcher.extract.extract_deal_from_dom') as mock_dom_extract, \
             patch.object(watcher, '_safe_on_new_deal') as mock_safe_deal:

            mock_html_extract.return_value = None  # HTML extraction fails
            mock_dom_extract.return_value = legacy_deal

            # Mock callback
            mock_callback = AsyncMock()

            await watcher._check_dom_for_deals(mock_callback)

            # Should have tried HTML extraction first
            mock_html_extract.assert_called_once()

            # Should have fallen back to DOM extraction
            mock_dom_extract.assert_called_once()
            mock_safe_deal.assert_called_once_with(legacy_deal, source="dom", on_new_deal=mock_callback)

    @pytest.mark.asyncio
    async def test_legacy_deal_conversion(self) -> None:
        """Test conversion of legacy Deal to DealDetails."""
        watcher = DealWatcher()

        # Mock legacy deal
        from app.models import Deal
        legacy_deal = Deal(
            title="Legacy Wine Name",
            price=55.00,
            vintage="2018",
            region="Bordeaux",
            url="http://example.com",
            bottle_size_ml=750
        )

        with patch.object(watcher, '_process_deal_details') as mock_process:

            mock_callback = AsyncMock()

            await watcher._safe_on_new_deal(legacy_deal, "network", mock_callback)

            # Should have converted to DealDetails and processed
            mock_process.assert_called_once()

            call_args = mock_process.call_args[0][0]  # First argument (deal_details)
            assert isinstance(call_args, DealDetails)
            assert call_args.wine_name == "Legacy Wine Name"
            assert call_args.vintage == 2018
            assert call_args.deal_price == 55.00
            assert call_args.bottle_size_ml == 750

            # Should also call legacy callback
            mock_callback.assert_called_once_with(legacy_deal)

    @pytest.mark.asyncio
    async def test_legacy_deal_conversion_invalid_vintage(self) -> None:
        """Test legacy deal conversion with invalid vintage."""
        watcher = DealWatcher()

        # Mock legacy deal with non-numeric vintage
        from app.models import Deal
        legacy_deal = Deal(
            title="Non-Vintage Wine",
            price=40.00,
            vintage="NV",  # Non-numeric
            region="California",
            url="http://example.com"
        )

        with patch.object(watcher, '_process_deal_details') as mock_process:

            mock_callback = AsyncMock()

            await watcher._safe_on_new_deal(legacy_deal, "test", mock_callback)

            # Should have converted to DealDetails with None vintage
            call_args = mock_process.call_args[0][0]
            assert call_args.vintage is None

    @pytest.mark.asyncio
    async def test_memory_cleanup(self) -> None:
        """Test that seen_deals memory cleanup is triggered."""
        watcher = DealWatcher()

        # Manually add many old entries to the seen_deals
        old_time = time.time() - 1000  # 1000 seconds ago
        for i in range(50):
            watcher.seen_deals[f"old_wine_{i}"] = old_time

        # Add 60 more recent deals to trigger cleanup (total > 100)
        with patch('app.watcher.extract.deal_key') as mock_key:
            for i in range(60):
                mock_key.return_value = f"new_wine_{i}"
                deal_details = DealDetails(wine_name=f"Wine {i}", deal_price=float(i + 1))

                with patch('app.watcher.enrich_deal'), \
                     patch('app.watcher.send_telegram_message'):
                    await watcher._process_deal_details(deal_details, "test")

            # Should have cleaned up old entries and kept recent ones
            assert len(watcher.seen_deals) <= 100

            # Should have removed old entries
            remaining_keys = list(watcher.seen_deals.keys())
            old_keys = [k for k in remaining_keys if k.startswith("old_wine_")]
            new_keys = [k for k in remaining_keys if k.startswith("new_wine_")]

            # Most old entries should be gone, new entries should remain
            assert len(old_keys) == 0  # Old entries should be cleaned up
            assert len(new_keys) > 0   # New entries should remain

    @pytest.mark.asyncio
    async def test_error_handling_robustness(self) -> None:
        """Test that errors in processing don't crash the watcher."""
        watcher = DealWatcher()

        deal_details = DealDetails(
            wine_name="Error Wine",
            deal_price=50.00
        )

        with patch('app.watcher.extract.deal_key') as mock_key:
            mock_key.side_effect = Exception("Key generation error")

            # Should not raise exception
            await watcher._process_deal_details(deal_details, "test")

            # Watcher should continue to function
            assert watcher.seen_deals is not None
