"""Tests for Vivino functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.vivino import (
    _extract_wine_data,
    _normalize_wine_name,
    _search_vivino_comprehensive,
    get_vivino_info,
)


class TestNormalizeWineName:
    """Tests for wine name normalization."""

    def test_normalize_basic_wine_name(self) -> None:
        """Test basic wine name normalization."""
        result = _normalize_wine_name("Caymus Cabernet Sauvignon")
        assert result == "Caymus Cabernet Sauvignon"

    def test_normalize_removes_wine_terms(self) -> None:
        """Test removal of common wine terms."""
        test_cases = [
            ("Caymus Red Wine", "Caymus"),
            ("Domaine White Wine", "Domaine"),
            ("Champagne Sparkling Wine", "Champagne"),
            ("Rosé Wine from Provence", "from Provence"),
        ]

        for input_name, expected in test_cases:
            result = _normalize_wine_name(input_name)
            assert result == expected

    def test_normalize_handles_extra_spaces(self) -> None:
        """Test handling of extra whitespace."""
        result = _normalize_wine_name("  Château   Margaux   Red   Wine  ")
        assert result == "Château Margaux"


class TestExtractWineData:
    """Tests for wine data extraction."""

    def test_extract_complete_data(self) -> None:
        """Test extraction of complete wine data."""
        wine_data = {
            "wine": {
                "average_rating": 4.2,
                "ratings_count": 1500,
                "price": 89.99
            }
        }

        result = _extract_wine_data(wine_data)
        assert result["rating"] == 4.2
        assert result["reviews"] == 1500
        assert result["price"] == 89.99

    def test_extract_flat_structure(self) -> None:
        """Test extraction from flat data structure."""
        wine_data = {
            "average_rating": 3.8,
            "reviews_count": 750,
            "average_price": 45.50
        }

        result = _extract_wine_data(wine_data)
        assert result["rating"] == 3.8
        assert result["reviews"] == 750
        assert result["price"] == 45.50

    def test_extract_nested_price_structure(self) -> None:
        """Test extraction from nested price structure."""
        wine_data = {
            "wine": {
                "rating": 4.5,
                "num_reviews": 2000,
                "price_data": {
                    "amount": 125.00
                }
            }
        }

        result = _extract_wine_data(wine_data)
        assert result["rating"] == 4.5
        assert result["reviews"] == 2000
        assert result["price"] == 125.00

    def test_extract_statistics_structure(self) -> None:
        """Test extraction from statistics structure."""
        wine_data = {
            "score": 4.1,
            "review_count": 500,
            "statistics": {
                "average_price": 75.25
            }
        }

        result = _extract_wine_data(wine_data)
        assert result["rating"] == 4.1
        assert result["reviews"] == 500
        assert result["price"] == 75.25

    def test_extract_partial_data(self) -> None:
        """Test extraction with missing fields."""
        wine_data = {
            "wine": {
                "average_rating": 3.9
                # Missing reviews and price
            }
        }

        result = _extract_wine_data(wine_data)
        assert result["rating"] == 3.9
        assert result["reviews"] is None
        assert result["price"] is None

    def test_extract_invalid_data(self) -> None:
        """Test extraction with invalid data types."""
        wine_data = {
            "average_rating": "invalid",
            "ratings_count": "not_a_number",
            "price": "not_a_price"
        }

        result = _extract_wine_data(wine_data)
        assert result["rating"] is None
        assert result["reviews"] is None
        assert result["price"] is None


class TestSearchVivinoComprehensive:
    """Tests for comprehensive Vivino search."""

    @pytest.mark.asyncio
    async def test_search_success_first_endpoint(self) -> None:
        """Test successful search on first endpoint."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "matches": [
                {
                    "wine": {
                        "average_rating": 4.3,
                        "ratings_count": 1200
                    }
                }
            ]
        }
        mock_client.get.return_value = mock_response

        result = await _search_vivino_comprehensive(mock_client, "test wine", "general")

        assert result is not None
        assert result["wine"]["average_rating"] == 4.3
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_fallback_endpoints(self) -> None:
        """Test fallback to alternative endpoints."""
        mock_client = AsyncMock()

        # First endpoint fails
        first_response = MagicMock()
        first_response.raise_for_status.side_effect = Exception("HTTP Error")

        # Second endpoint succeeds
        second_response = MagicMock()
        second_response.raise_for_status.return_value = None
        second_response.json.return_value = {
            "results": [
                {
                    "average_rating": 4.0,
                    "reviews_count": 800
                }
            ]
        }

        mock_client.get.side_effect = [first_response, second_response]

        result = await _search_vivino_comprehensive(mock_client, "test wine", "general")

        assert result is not None
        assert result["average_rating"] == 4.0
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_search_no_results(self) -> None:
        """Test search with no results."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"matches": []}
        mock_client.get.return_value = mock_response

        result = await _search_vivino_comprehensive(mock_client, "nonexistent wine", "general")

        assert result is None


class TestGetVivinoInfo:
    """Tests for the main get_vivino_info function."""

    @pytest.mark.asyncio
    async def test_get_info_with_vintage(self) -> None:
        """Test getting info with vintage specified."""
        vintage_data = {
            "wine": {
                "average_rating": 4.5,
                "ratings_count": 1000,
                "price": 95.00
            }
        }

        general_data = {
            "wine": {
                "average_rating": 4.2,
                "ratings_count": 5000,
                "price": 85.00
            }
        }

        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            mock_search.side_effect = [vintage_data, general_data]

            result = await get_vivino_info("Caymus Cabernet Sauvignon", 2019)

            assert result["vintage_rating"] == 4.5
            assert result["vintage_price"] == 95.00
            assert result["vintage_reviews"] == 1000
            assert result["overall_rating"] == 4.2
            assert result["overall_price"] == 85.00
            assert result["overall_reviews"] == 5000

            # Should have made two searches
            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_get_info_without_vintage(self) -> None:
        """Test getting info without vintage."""
        general_data = {
            "wine": {
                "average_rating": 4.1,
                "ratings_count": 2500,
                "price": 75.00
            }
        }

        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            mock_search.return_value = general_data

            result = await get_vivino_info("Domaine de la Côte Pinot Noir")

            assert result["vintage_rating"] is None
            assert result["vintage_price"] is None
            assert result["vintage_reviews"] is None
            assert result["overall_rating"] == 4.1
            assert result["overall_price"] == 75.00
            assert result["overall_reviews"] == 2500

            # Should have made only one search (no vintage)
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_info_vintage_fails_general_succeeds(self) -> None:
        """Test when vintage search fails but general succeeds."""
        general_data = {
            "wine": {
                "average_rating": 3.8,
                "ratings_count": 1500
            }
        }

        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            # First call (vintage) returns None, second call (general) returns data
            mock_search.side_effect = [None, general_data]

            result = await get_vivino_info("Rare Wine", 1985)

            assert result["vintage_rating"] is None
            assert result["vintage_price"] is None
            assert result["vintage_reviews"] is None
            assert result["overall_rating"] == 3.8
            assert result["overall_reviews"] == 1500

            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_get_info_both_searches_fail(self) -> None:
        """Test when both searches fail."""
        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            mock_search.return_value = None

            result = await get_vivino_info("Nonexistent Wine", 2020)

            # All fields should be None
            assert all(value is None for value in result.values())

            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_get_info_timeout_handling(self) -> None:
        """Test timeout handling."""
        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            mock_search.side_effect = TimeoutError("Request timed out")

            result = await get_vivino_info("Test Wine")

            # Should return empty result on timeout
            assert all(value is None for value in result.values())

    @pytest.mark.asyncio
    async def test_get_info_partial_data(self) -> None:
        """Test handling of partial data."""
        vintage_data = {
            "wine": {
                "average_rating": 4.3
                # Missing price and reviews
            }
        }

        general_data = {
            "wine": {
                "ratings_count": 3000,
                "price": 120.00
                # Missing rating
            }
        }

        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            mock_search.side_effect = [vintage_data, general_data]

            result = await get_vivino_info("Partial Data Wine", 2018)

            assert result["vintage_rating"] == 4.3
            assert result["vintage_price"] is None
            assert result["vintage_reviews"] is None
            assert result["overall_rating"] is None
            assert result["overall_price"] == 120.00
            assert result["overall_reviews"] == 3000

    @pytest.mark.asyncio
    async def test_get_info_wine_name_normalization(self) -> None:
        """Test that wine names are properly normalized."""
        with patch('app.vivino._search_vivino_comprehensive') as mock_search, \
             patch('app.vivino._normalize_wine_name') as mock_normalize:

            mock_normalize.return_value = "Normalized Wine"
            mock_search.return_value = None

            await get_vivino_info("Original Wine Name Red Wine", 2020)

            # Should normalize the wine name
            mock_normalize.assert_called_once_with("Original Wine Name Red Wine")

            # Should use normalized name in searches
            expected_calls = [
                ("Normalized Wine 2020", "vintage"),
                ("Normalized Wine", "general")
            ]

            actual_calls = [(call.args[1], call.args[2]) for call in mock_search.call_args_list]
            assert actual_calls == expected_calls


class TestVivinoIntegration:
    """Integration tests for Vivino functionality."""

    @pytest.mark.asyncio
    async def test_real_wine_search_format(self) -> None:
        """Test with realistic wine data format."""
        # Mock a realistic Vivino API response
        realistic_response = {
            "matches": [
                {
                    "wine": {
                        "id": 123456,
                        "name": "Caymus Cabernet Sauvignon",
                        "average_rating": 4.2,
                        "ratings_count": 15420,
                        "price": {
                            "amount": 89.99,
                            "currency": "USD"
                        },
                        "vintage": {
                            "year": 2019
                        },
                        "region": {
                            "name": "Napa Valley"
                        }
                    }
                }
            ]
        }

        with patch('app.vivino._search_vivino_comprehensive') as mock_search:
            mock_search.return_value = realistic_response["matches"][0]

            result = await get_vivino_info("Caymus Cabernet Sauvignon", 2019)

            assert result["vintage_rating"] == 4.2
            assert result["vintage_reviews"] == 15420
            # Price extraction might need adjustment based on actual API structure

    def test_error_handling_in_extract(self) -> None:
        """Test error handling in data extraction."""
        # Test with completely malformed data
        malformed_data = {
            "completely": {
                "different": {
                    "structure": "that should not crash"
                }
            }
        }

        result = _extract_wine_data(malformed_data)

        # Should not crash and return None values
        assert result["rating"] is None
        assert result["price"] is None
        assert result["reviews"] is None

