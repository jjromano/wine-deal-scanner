"""Tests for data models."""

import pytest

from app.models import normalize_bottle_size


class TestNormalizeBottleSize:
    """Tests for the normalize_bottle_size function."""

    @pytest.mark.parametrize("text,expected", [
        ("Napa Cab 2020 (Magnum 1.5L)", 1500),
        ("Barolo NV 375 ml", 375),
        ("Champagne Brut (Split 187ML)", 187),
        ("Rhone Rouge 0.75 L", 750),
        ("Just a wine title with no size", 750),
        ("Double Magnum 3L", 3000),
        # Additional test cases
        ("Burgundy Half Bottle", 375),
        ("Demi bottle of Chablis", 375),
        ("Imperial 6L Bordeaux", 6000),
        ("Jeroboam Champagne", 3000),
        ("Piccolo Prosecco", 187),
        ("1000 ml bottle", 1000),
        ("500ml size", 500),
        ("2.5 L bottle", 2500),
        ("720ml Japanese sake style", 720),
        ("Empty string should default", 750),
        (None, 750),
    ])
    def test_normalize_bottle_size(self, text: str, expected: int) -> None:
        """Test bottle size normalization with various formats."""
        assert normalize_bottle_size(text) == expected

    def test_normalize_bottle_size_case_insensitive(self) -> None:
        """Test that bottle size detection is case insensitive."""
        assert normalize_bottle_size("MAGNUM 1.5L") == 1500
        assert normalize_bottle_size("magnum 1.5l") == 1500
        assert normalize_bottle_size("Magnum 1.5L") == 1500

    def test_normalize_bottle_size_with_multiple_matches(self) -> None:
        """Test that first match wins when multiple sizes are mentioned."""
        # Should pick up the first pattern match (187ml)
        text = "Split 187ml or maybe it's actually a 750ml bottle"
        assert normalize_bottle_size(text) == 187

    def test_normalize_bottle_size_edge_cases(self) -> None:
        """Test edge cases and boundary conditions."""
        # Very small sizes should be ignored by ml fallback
        assert normalize_bottle_size("50ml miniature") == 750

        # Very large sizes should be ignored by ml fallback
        assert normalize_bottle_size("7000ml huge bottle") == 750

        # Invalid number formats - should not match due to double decimal
        assert normalize_bottle_size("invalid format no numbers") == 750

        # Numbers without proper units
        assert normalize_bottle_size("Just 1500 without units") == 750
