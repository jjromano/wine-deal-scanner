"""Tests for deal enrichment functionality."""

from unittest.mock import patch

import pytest

from app.enrichment import enrich_deal
from app.models import DealDetails, EnrichedDeal


class TestEnrichedDealModel:
    """Tests for the EnrichedDeal Pydantic model."""

    def test_enriched_deal_creation(self) -> None:
        """Test creating EnrichedDeal instance."""
        enriched = EnrichedDeal(
            wine_name="Test Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=45.99,
            vintage_rating=4.2,
            vintage_price=65.00,
            vintage_reviews=1200,
            overall_rating=4.0,
            overall_price=60.00,
            overall_reviews=5000
        )

        assert enriched.wine_name == "Test Wine"
        assert enriched.vintage == 2020
        assert enriched.bottle_size_ml == 750
        assert enriched.deal_price == 45.99
        assert enriched.vintage_rating == 4.2
        assert enriched.vintage_price == 65.00
        assert enriched.vintage_reviews == 1200
        assert enriched.overall_rating == 4.0
        assert enriched.overall_price == 60.00
        assert enriched.overall_reviews == 5000

    def test_enriched_deal_minimal_data(self) -> None:
        """Test EnrichedDeal with minimal required data."""
        enriched = EnrichedDeal(
            wine_name="Minimal Wine",
            deal_price=25.99
        )

        assert enriched.wine_name == "Minimal Wine"
        assert enriched.vintage is None
        assert enriched.bottle_size_ml == 750  # Default
        assert enriched.deal_price == 25.99
        assert enriched.vintage_rating is None
        assert enriched.vintage_price is None
        assert enriched.vintage_reviews is None
        assert enriched.overall_rating is None
        assert enriched.overall_price is None
        assert enriched.overall_reviews is None

    def test_enriched_deal_string_representation(self) -> None:
        """Test string representation of EnrichedDeal."""
        # With both vintage and overall ratings
        enriched1 = EnrichedDeal(
            wine_name="Cabernet Sauvignon",
            vintage=2019,
            deal_price=35.99,
            vintage_rating=4.5,
            overall_rating=4.2
        )
        expected1 = "Cabernet Sauvignon 2019: $35.99 [Vintage: 4.5★, Overall: 4.2★]"
        assert str(enriched1) == expected1

        # With only overall rating
        enriched2 = EnrichedDeal(
            wine_name="Champagne",
            bottle_size_ml=1500,
            deal_price=125.00,
            overall_rating=4.3
        )
        expected2 = "Champagne (1500ml): $125.00 [Overall: 4.3★]"
        assert str(enriched2) == expected2

        # No ratings
        enriched3 = EnrichedDeal(
            wine_name="House Red",
            deal_price=15.99
        )
        expected3 = "House Red: $15.99"
        assert str(enriched3) == expected3

    def test_has_vivino_data_property(self) -> None:
        """Test has_vivino_data property."""
        # No Vivino data
        enriched1 = EnrichedDeal(
            wine_name="No Data Wine",
            deal_price=30.00
        )
        assert not enriched1.has_vivino_data

        # Has vintage data
        enriched2 = EnrichedDeal(
            wine_name="Vintage Data Wine",
            deal_price=40.00,
            vintage_rating=4.1
        )
        assert enriched2.has_vivino_data

        # Has overall data
        enriched3 = EnrichedDeal(
            wine_name="Overall Data Wine",
            deal_price=50.00,
            overall_price=70.00
        )
        assert enriched3.has_vivino_data

    def test_best_rating_property(self) -> None:
        """Test best_rating property."""
        # No ratings
        enriched1 = EnrichedDeal(
            wine_name="No Rating Wine",
            deal_price=30.00
        )
        assert enriched1.best_rating is None

        # Only overall rating
        enriched2 = EnrichedDeal(
            wine_name="Overall Rating Wine",
            deal_price=40.00,
            overall_rating=4.0
        )
        assert enriched2.best_rating == 4.0

        # Only vintage rating
        enriched3 = EnrichedDeal(
            wine_name="Vintage Rating Wine",
            deal_price=50.00,
            vintage_rating=4.3
        )
        assert enriched3.best_rating == 4.3

        # Both ratings (vintage preferred)
        enriched4 = EnrichedDeal(
            wine_name="Both Ratings Wine",
            deal_price=60.00,
            vintage_rating=4.5,
            overall_rating=4.1
        )
        assert enriched4.best_rating == 4.5

    def test_best_price_comparison_property(self) -> None:
        """Test best_price_comparison property."""
        # No Vivino price
        enriched1 = EnrichedDeal(
            wine_name="No Price Wine",
            deal_price=30.00
        )
        comparison1 = enriched1.best_price_comparison
        assert comparison1["vivino_price"] is None
        assert comparison1["savings"] is None
        assert comparison1["savings_percent"] is None

        # Only overall price
        enriched2 = EnrichedDeal(
            wine_name="Overall Price Wine",
            deal_price=40.00,
            overall_price=60.00
        )
        comparison2 = enriched2.best_price_comparison
        assert comparison2["vivino_price"] == 60.00
        assert comparison2["savings"] == 20.00
        assert abs(comparison2["savings_percent"] - 33.333333333333336) < 0.01

        # Only vintage price
        enriched3 = EnrichedDeal(
            wine_name="Vintage Price Wine",
            deal_price=50.00,
            vintage_price=80.00
        )
        comparison3 = enriched3.best_price_comparison
        assert comparison3["vivino_price"] == 80.00
        assert comparison3["savings"] == 30.00
        assert comparison3["savings_percent"] == 37.5

        # Both prices (vintage preferred)
        enriched4 = EnrichedDeal(
            wine_name="Both Prices Wine",
            deal_price=45.00,
            vintage_price=70.00,
            overall_price=65.00
        )
        comparison4 = enriched4.best_price_comparison
        assert comparison4["vivino_price"] == 70.00
        assert comparison4["savings"] == 25.00
        assert abs(comparison4["savings_percent"] - 35.714285714285715) < 0.01

        # Deal price higher than Vivino (negative savings)
        enriched5 = EnrichedDeal(
            wine_name="Expensive Deal Wine",
            deal_price=100.00,
            overall_price=80.00
        )
        comparison5 = enriched5.best_price_comparison
        assert comparison5["vivino_price"] == 80.00
        assert comparison5["savings"] == -20.00
        assert comparison5["savings_percent"] == -25.0

    def test_enriched_deal_validation(self) -> None:
        """Test EnrichedDeal field validation."""
        # Valid ratings (1-5 range)
        enriched = EnrichedDeal(
            wine_name="Valid Wine",
            deal_price=30.00,
            vintage_rating=4.5,
            overall_rating=3.8
        )
        assert enriched.vintage_rating == 4.5
        assert enriched.overall_rating == 3.8

        # Invalid rating (too high)
        with pytest.raises(ValueError):
            EnrichedDeal(
                wine_name="Invalid High Rating",
                deal_price=30.00,
                vintage_rating=6.0
            )

        # Invalid rating (too low)
        with pytest.raises(ValueError):
            EnrichedDeal(
                wine_name="Invalid Low Rating",
                deal_price=30.00,
                overall_rating=0.5
            )

        # Invalid price (negative)
        with pytest.raises(ValueError):
            EnrichedDeal(
                wine_name="Invalid Price",
                deal_price=-10.00
            )

        # Invalid reviews (negative)
        with pytest.raises(ValueError):
            EnrichedDeal(
                wine_name="Invalid Reviews",
                deal_price=30.00,
                vintage_reviews=-100
            )


class TestEnrichDealFunction:
    """Tests for the enrich_deal function."""

    @pytest.mark.asyncio
    async def test_enrich_deal_complete_data(self) -> None:
        """Test enriching deal with complete Vivino data."""
        deal = DealDetails(
            wine_name="Caymus Cabernet Sauvignon",
            vintage=2019,
            bottle_size_ml=750,
            deal_price=85.99
        )

        vivino_data = {
            "vintage_rating": 4.3,
            "vintage_price": 120.00,
            "vintage_reviews": 1500,
            "overall_rating": 4.1,
            "overall_price": 110.00,
            "overall_reviews": 8000
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_data

            result = await enrich_deal(deal)

            assert isinstance(result, EnrichedDeal)
            assert result.wine_name == "Caymus Cabernet Sauvignon"
            assert result.vintage == 2019
            assert result.bottle_size_ml == 750
            assert result.deal_price == 85.99

            assert result.vintage_rating == 4.3
            assert result.vintage_price == 120.00
            assert result.vintage_reviews == 1500
            assert result.overall_rating == 4.1
            assert result.overall_price == 110.00
            assert result.overall_reviews == 8000

            assert result.has_vivino_data
            assert result.best_rating == 4.3

            mock_vivino.assert_called_once_with("Caymus Cabernet Sauvignon", 2019)

    @pytest.mark.asyncio
    async def test_enrich_deal_partial_data(self) -> None:
        """Test enriching deal with partial Vivino data."""
        deal = DealDetails(
            wine_name="Partial Data Wine",
            vintage=2020,
            deal_price=45.00
        )

        vivino_data = {
            "vintage_rating": None,
            "vintage_price": None,
            "vintage_reviews": None,
            "overall_rating": 3.9,
            "overall_price": 55.00,
            "overall_reviews": 2500
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_data

            result = await enrich_deal(deal)

            assert result.vintage_rating is None
            assert result.vintage_price is None
            assert result.vintage_reviews is None
            assert result.overall_rating == 3.9
            assert result.overall_price == 55.00
            assert result.overall_reviews == 2500

            assert result.has_vivino_data
            assert result.best_rating == 3.9

            price_comparison = result.best_price_comparison
            assert price_comparison["vivino_price"] == 55.00
            assert price_comparison["savings"] == 10.00

    @pytest.mark.asyncio
    async def test_enrich_deal_no_vivino_data(self) -> None:
        """Test enriching deal when no Vivino data is found."""
        deal = DealDetails(
            wine_name="Unknown Wine",
            vintage=2018,
            deal_price=25.99
        )

        vivino_data = {
            "vintage_rating": None,
            "vintage_price": None,
            "vintage_reviews": None,
            "overall_rating": None,
            "overall_price": None,
            "overall_reviews": None
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_data

            result = await enrich_deal(deal)

            assert result.wine_name == "Unknown Wine"
            assert result.vintage == 2018
            assert result.deal_price == 25.99

            assert not result.has_vivino_data
            assert result.best_rating is None

            price_comparison = result.best_price_comparison
            assert price_comparison["vivino_price"] is None
            assert price_comparison["savings"] is None
            assert price_comparison["savings_percent"] is None

    @pytest.mark.asyncio
    async def test_enrich_deal_no_vintage(self) -> None:
        """Test enriching deal without vintage."""
        deal = DealDetails(
            wine_name="Non-Vintage Wine",
            deal_price=35.00
        )

        vivino_data = {
            "vintage_rating": None,
            "vintage_price": None,
            "vintage_reviews": None,
            "overall_rating": 4.0,
            "overall_price": 45.00,
            "overall_reviews": 3200
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_data

            result = await enrich_deal(deal)

            assert result.vintage is None
            assert result.overall_rating == 4.0
            assert result.overall_price == 45.00
            assert result.overall_reviews == 3200

            # Should call Vivino with None vintage
            mock_vivino.assert_called_once_with("Non-Vintage Wine", None)

    @pytest.mark.asyncio
    async def test_enrich_deal_vivino_error(self) -> None:
        """Test enriching deal when Vivino lookup fails."""
        deal = DealDetails(
            wine_name="Error Wine",
            vintage=2021,
            deal_price=50.00
        )

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.side_effect = Exception("Vivino API error")

            result = await enrich_deal(deal)

            # Should still create enriched deal with no Vivino data
            assert result.wine_name == "Error Wine"
            assert result.vintage == 2021
            assert result.deal_price == 50.00

            assert not result.has_vivino_data
            assert all(v is None for v in [
                result.vintage_rating, result.vintage_price, result.vintage_reviews,
                result.overall_rating, result.overall_price, result.overall_reviews
            ])

    @pytest.mark.asyncio
    async def test_enrich_deal_different_bottle_sizes(self) -> None:
        """Test enriching deals with different bottle sizes."""
        # Magnum bottle
        deal_magnum = DealDetails(
            wine_name="Magnum Champagne",
            vintage=2018,
            bottle_size_ml=1500,
            deal_price=199.99
        )

        vivino_data = {
            "vintage_rating": 4.4,
            "vintage_price": 250.00,
            "vintage_reviews": 800,
            "overall_rating": 4.2,
            "overall_price": 230.00,
            "overall_reviews": 4500
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_data

            result = await enrich_deal(deal_magnum)

            assert result.bottle_size_ml == 1500
            assert result.vintage_rating == 4.4
            assert result.vintage_price == 250.00

            # Check string representation includes bottle size
            str_repr = str(result)
            assert "(1500ml)" in str_repr

    @pytest.mark.asyncio
    async def test_enrich_deal_price_savings_calculation(self) -> None:
        """Test price savings calculation in enriched deals."""
        deal = DealDetails(
            wine_name="Savings Test Wine",
            vintage=2020,
            deal_price=60.00
        )

        vivino_data = {
            "vintage_rating": 4.2,
            "vintage_price": 90.00,
            "vintage_reviews": 1200,
            "overall_rating": 4.0,
            "overall_price": 85.00,
            "overall_reviews": 5000
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_data

            result = await enrich_deal(deal)

            price_comparison = result.best_price_comparison

            # Should prefer vintage price (90.00)
            assert price_comparison["vivino_price"] == 90.00
            assert price_comparison["savings"] == 30.00  # 90 - 60
            assert abs(price_comparison["savings_percent"] - 33.333333333333336) < 0.01  # 30/90 * 100


class TestEnrichmentIntegration:
    """Integration tests for enrichment functionality."""

    @pytest.mark.asyncio
    async def test_full_enrichment_workflow(self) -> None:
        """Test complete enrichment workflow from deal to enriched deal."""
        # Create a realistic deal
        deal = DealDetails(
            wine_name="Château Margaux",
            vintage=2015,
            bottle_size_ml=750,
            deal_price=849.99
        )

        # Mock realistic Vivino response
        vivino_response = {
            "vintage_rating": 4.6,
            "vintage_price": 1200.00,
            "vintage_reviews": 450,
            "overall_rating": 4.5,
            "overall_price": 1100.00,
            "overall_reviews": 2800
        }

        with patch('app.enrichment.get_vivino_info') as mock_vivino:
            mock_vivino.return_value = vivino_response

            enriched = await enrich_deal(deal)

            # Verify all data is properly transferred
            assert enriched.wine_name == "Château Margaux"
            assert enriched.vintage == 2015
            assert enriched.bottle_size_ml == 750
            assert enriched.deal_price == 849.99

            assert enriched.vintage_rating == 4.6
            assert enriched.vintage_price == 1200.00
            assert enriched.vintage_reviews == 450
            assert enriched.overall_rating == 4.5
            assert enriched.overall_price == 1100.00
            assert enriched.overall_reviews == 2800

            # Verify computed properties
            assert enriched.has_vivino_data
            assert enriched.best_rating == 4.6  # Vintage preferred

            price_comparison = enriched.best_price_comparison
            assert price_comparison["vivino_price"] == 1200.00  # Vintage price preferred
            assert price_comparison["savings"] == 350.01  # 1200 - 849.99
            assert abs(price_comparison["savings_percent"] - 29.167583333333332) < 0.01

            # Verify string representation
            str_repr = str(enriched)
            expected = "Château Margaux 2015: $849.99 [Vintage: 4.6★, Overall: 4.5★]"
            assert str_repr == expected

