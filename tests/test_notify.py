"""Tests for Telegram notification functionality."""

from unittest.mock import patch

import pytest

from app.models import EnrichedDeal
from app.notify import (
    TelegramError,
    _format_enriched_deal_message,
    send_telegram_message,
)


class TestFormatEnrichedDealMessage:
    """Tests for enriched deal message formatting."""

    def test_format_complete_enriched_deal(self) -> None:
        """Test formatting deal with complete Vivino data."""
        enriched = EnrichedDeal(
            wine_name="Caymus Cabernet Sauvignon",
            vintage=2019,
            bottle_size_ml=750,
            deal_price=85.99,
            vintage_rating=4.3,
            vintage_price=120.00,
            vintage_reviews=1500,
            overall_rating=4.1,
            overall_price=110.00,
            overall_reviews=8000
        )

        message = _format_enriched_deal_message(enriched)

        # Check header
        assert "🍷 New Deal: Caymus Cabernet Sauvignon 2019" in message

        # Check basic info
        assert "Size: 750ml" in message
        assert "Deal Price: $85.99" in message

        # Check vintage data
        assert "Vivino (vintage): 4.3⭐ — avg ($120.00) — 1500 reviews" in message

        # Check overall data
        assert "Vivino (overall): 4.1⭐ — avg ($110.00) — 8000 reviews" in message

        # Check savings calculation
        assert "💰 Save $34.01 (28.3% off Vivino avg)" in message

    def test_format_no_vintage_wine(self) -> None:
        """Test formatting wine without vintage."""
        enriched = EnrichedDeal(
            wine_name="House Red Blend",
            bottle_size_ml=750,
            deal_price=18.99,
            overall_rating=3.8,
            overall_price=25.00,
            overall_reviews=2500
        )

        message = _format_enriched_deal_message(enriched)

        # Should not have vintage in header
        assert "🍷 New Deal: House Red Blend" in message
        assert "2019" not in message

        # Should have overall data only
        assert "Vivino (overall): 3.8⭐ — avg ($25.00) — 2500 reviews" in message
        assert "Vivino (vintage):" not in message

        # Should show savings
        assert "💰 Save $6.01 (24.0% off Vivino avg)" in message

    def test_format_magnum_bottle(self) -> None:
        """Test formatting magnum bottle."""
        enriched = EnrichedDeal(
            wine_name="Dom Pérignon Champagne",
            vintage=2012,
            bottle_size_ml=1500,
            deal_price=299.99,
            vintage_rating=4.6,
            vintage_reviews=800
        )

        message = _format_enriched_deal_message(enriched)

        assert "Size: 1500ml" in message
        assert "Vivino (vintage): 4.6⭐ — 800 reviews" in message
        # Should not have price info if not available
        assert "avg ($" not in message

    def test_format_partial_vivino_data(self) -> None:
        """Test formatting with partial Vivino data."""
        enriched = EnrichedDeal(
            wine_name="Partial Data Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=45.00,
            vintage_rating=4.2,  # Only rating, no price or reviews
            overall_price=55.00,  # Only price, no rating or reviews
            overall_reviews=3000  # Only reviews
        )

        message = _format_enriched_deal_message(enriched)

        # Vintage line should only have rating
        assert "Vivino (vintage): 4.2⭐" in message
        assert "Vivino (vintage): 4.2⭐ — avg" not in message

        # Overall line should have price and reviews
        assert "Vivino (overall): avg ($55.00) — 3000 reviews" in message

        # Should show savings based on overall price
        assert "💰 Save $10.00 (18.2% off Vivino avg)" in message

    def test_format_no_vivino_data(self) -> None:
        """Test formatting with no Vivino data."""
        enriched = EnrichedDeal(
            wine_name="Unknown Wine",
            vintage=2021,
            bottle_size_ml=750,
            deal_price=35.00
        )

        message = _format_enriched_deal_message(enriched)

        # Should have basic info
        assert "🍷 New Deal: Unknown Wine 2021" in message
        assert "Size: 750ml" in message
        assert "Deal Price: $35.00" in message

        # Should not have Vivino data
        assert "Vivino (vintage):" not in message
        assert "Vivino (overall):" not in message
        assert "💰 Save" not in message

    def test_format_expensive_deal(self) -> None:
        """Test formatting when deal price is higher than Vivino."""
        enriched = EnrichedDeal(
            wine_name="Expensive Wine",
            vintage=2018,
            bottle_size_ml=750,
            deal_price=100.00,
            overall_rating=3.5,
            overall_price=80.00,
            overall_reviews=1200
        )

        message = _format_enriched_deal_message(enriched)

        # Should have Vivino data
        assert "Vivino (overall): 3.5⭐ — avg ($80.00) — 1200 reviews" in message

        # Should NOT show savings (negative savings)
        assert "💰 Save" not in message

    def test_format_mixed_vivino_data(self) -> None:
        """Test formatting with mixed vintage and overall data."""
        enriched = EnrichedDeal(
            wine_name="Mixed Data Wine",
            vintage=2017,
            bottle_size_ml=750,
            deal_price=65.00,
            vintage_price=90.00,
            vintage_reviews=500,  # No vintage rating
            overall_rating=4.0,
            overall_reviews=2000  # No overall price
        )

        message = _format_enriched_deal_message(enriched)

        # Vintage line should have price and reviews only
        assert "Vivino (vintage): avg ($90.00) — 500 reviews" in message

        # Overall line should have rating and reviews only
        assert "Vivino (overall): 4.0⭐ — 2000 reviews" in message

        # Should show savings based on vintage price (preferred)
        assert "💰 Save $25.00 (27.8% off Vivino avg)" in message


class TestSendTelegramMessage:
    """Tests for the send_telegram_message function."""

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """Test successful message sending."""
        enriched = EnrichedDeal(
            wine_name="Test Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=50.00,
            overall_rating=4.2,
            overall_price=65.00,
            overall_reviews=1500
        )

        with patch('app.notify._send_telegram_message') as mock_send:
            mock_send.return_value = True

            result = await send_telegram_message(enriched)

            assert result is True
            mock_send.assert_called_once()

            # Check the formatted message was passed
            call_args = mock_send.call_args
            message = call_args[0][1]  # Second argument is the message
            assert "🍷 New Deal: Test Wine 2020" in message
            assert "Deal Price: $50.00" in message

    @pytest.mark.asyncio
    async def test_send_message_telegram_error(self) -> None:
        """Test handling of Telegram API errors."""
        enriched = EnrichedDeal(
            wine_name="Error Wine",
            deal_price=30.00
        )

        with patch('app.notify._send_telegram_message') as mock_send:
            mock_send.side_effect = TelegramError("API Error")

            result = await send_telegram_message(enriched)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_timeout(self) -> None:
        """Test handling of timeout errors."""
        enriched = EnrichedDeal(
            wine_name="Timeout Wine",
            deal_price=40.00
        )

        with patch('app.notify._send_telegram_message') as mock_send:
            mock_send.side_effect = TimeoutError("Request timed out")

            result = await send_telegram_message(enriched, timeout_s=1.0)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_unexpected_error(self) -> None:
        """Test handling of unexpected errors."""
        enriched = EnrichedDeal(
            wine_name="Exception Wine",
            deal_price=35.00
        )

        with patch('app.notify._send_telegram_message') as mock_send:
            mock_send.side_effect = Exception("Unexpected error")

            result = await send_telegram_message(enriched)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_custom_timeout(self) -> None:
        """Test sending message with custom timeout."""
        enriched = EnrichedDeal(
            wine_name="Custom Timeout Wine",
            deal_price=25.00
        )

        with patch('app.notify._send_telegram_message') as mock_send:
            mock_send.return_value = True

            result = await send_telegram_message(enriched, timeout_s=15.0)

            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_logging(self) -> None:
        """Test that appropriate logging occurs."""
        enriched = EnrichedDeal(
            wine_name="Logging Test Wine",
            vintage=2019,
            deal_price=75.00
        )

        with patch('app.notify._send_telegram_message') as mock_send, \
             patch('app.notify.logger') as mock_logger, \
             patch('app.notify.TELEGRAM_CHAT_ID', 'test_chat_id'):

            mock_send.return_value = True

            await send_telegram_message(enriched)

            # Check that info log was called for starting
            mock_logger.info.assert_any_call(
                "Sending Telegram notification",
                wine_name="Logging Test Wine",
                vintage=2019,
                deal_price=75.00,
                has_vivino_data=False
            )

            # Check that success log was called
            mock_logger.info.assert_any_call(
                "Telegram notification sent successfully",
                wine_name="Logging Test Wine",
                vintage=2019,
                chat_id='test_chat_id'
            )

    @pytest.mark.asyncio
    async def test_send_message_error_logging(self) -> None:
        """Test error logging on failure."""
        enriched = EnrichedDeal(
            wine_name="Error Logging Wine",
            deal_price=45.00
        )

        with patch('app.notify._send_telegram_message') as mock_send, \
             patch('app.notify.logger') as mock_logger:

            mock_send.side_effect = TelegramError("Test error")

            await send_telegram_message(enriched)

            # Check that error log was called
            mock_logger.error.assert_called_with(
                "Telegram API error",
                wine_name="Error Logging Wine",
                error="Test error"
            )


class TestMessageFormatting:
    """Tests for message formatting edge cases."""

    def test_message_formatting_special_characters(self) -> None:
        """Test message formatting with special characters in wine name."""
        enriched = EnrichedDeal(
            wine_name="Château d'Yquem & Co. (Special Edition)",
            vintage=2015,
            bottle_size_ml=375,
            deal_price=299.99
        )

        message = _format_enriched_deal_message(enriched)

        # Should handle special characters properly
        assert "🍷 New Deal: Château d'Yquem & Co. (Special Edition) 2015" in message
        assert "Size: 375ml" in message

    def test_message_formatting_long_wine_name(self) -> None:
        """Test message formatting with very long wine name."""
        enriched = EnrichedDeal(
            wine_name="Very Long Wine Name That Goes On And On With Multiple Words And Descriptors",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=89.99
        )

        message = _format_enriched_deal_message(enriched)

        # Should handle long names without issues
        assert "Very Long Wine Name That Goes On And On" in message

    def test_message_formatting_zero_savings(self) -> None:
        """Test message formatting when savings is exactly zero."""
        enriched = EnrichedDeal(
            wine_name="Zero Savings Wine",
            deal_price=50.00,
            overall_price=50.00,  # Same price as deal
            overall_rating=4.0
        )

        message = _format_enriched_deal_message(enriched)

        # Should not show savings when it's zero
        assert "💰 Save" not in message

    def test_message_formatting_high_precision_values(self) -> None:
        """Test message formatting with high precision decimal values."""
        enriched = EnrichedDeal(
            wine_name="Precision Wine",
            deal_price=33.333,  # Will be rounded to 2 decimals
            vintage_rating=4.567,  # Will be rounded to 1 decimal
            vintage_price=44.999,  # Will be rounded to 2 decimals
            vintage_reviews=1234
        )

        message = _format_enriched_deal_message(enriched)

        # Check proper decimal formatting
        assert "Deal Price: $33.33" in message
        assert "4.6⭐" in message
        assert "avg ($45.00)" in message


class TestTelegramIntegration:
    """Integration tests for Telegram functionality."""

    @pytest.mark.asyncio
    async def test_full_telegram_workflow(self) -> None:
        """Test complete Telegram workflow."""
        # Create a realistic enriched deal
        enriched = EnrichedDeal(
            wine_name="Opus One",
            vintage=2018,
            bottle_size_ml=750,
            deal_price=349.99,
            vintage_rating=4.4,
            vintage_price=450.00,
            vintage_reviews=850,
            overall_rating=4.3,
            overall_price=425.00,
            overall_reviews=5200
        )

        with patch('app.notify._send_telegram_message') as mock_send:
            mock_send.return_value = True

            result = await send_telegram_message(enriched)

            assert result is True

            # Verify the formatted message content
            call_args = mock_send.call_args
            message = call_args[0][1]

            # Check all expected components
            assert "🍷 New Deal: Opus One 2018" in message
            assert "Size: 750ml" in message
            assert "Deal Price: $349.99" in message
            assert "Vivino (vintage): 4.4⭐ — avg ($450.00) — 850 reviews" in message
            assert "Vivino (overall): 4.3⭐ — avg ($425.00) — 5200 reviews" in message
            assert "💰 Save $100.01 (22.2% off Vivino avg)" in message

    def test_message_structure_consistency(self) -> None:
        """Test that message structure is consistent across different inputs."""
        test_cases = [
            # Minimal deal
            EnrichedDeal(wine_name="Basic Wine", deal_price=20.00),

            # Deal with vintage only
            EnrichedDeal(wine_name="Vintage Wine", vintage=2019, deal_price=35.00),

            # Deal with Vivino data
            EnrichedDeal(
                wine_name="Vivino Wine",
                deal_price=50.00,
                overall_rating=4.0,
                overall_reviews=1000
            ),

            # Complete deal
            EnrichedDeal(
                wine_name="Complete Wine",
                vintage=2020,
                bottle_size_ml=1500,
                deal_price=125.00,
                vintage_rating=4.5,
                vintage_price=180.00,
                vintage_reviews=500,
                overall_rating=4.2,
                overall_price=170.00,
                overall_reviews=2500
            )
        ]

        for enriched in test_cases:
            message = _format_enriched_deal_message(enriched)

            # All messages should start with wine emoji
            assert message.startswith("🍷 New Deal:")

            # All messages should have size and price
            assert "Size:" in message
            assert "Deal Price:" in message

            # Message should be non-empty and reasonable length
            assert len(message) > 20
            assert len(message) < 1000  # Reasonable upper bound
