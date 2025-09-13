"""Tests for HTML extraction functionality."""

import pytest

from app.extract import extract_deal_details
from app.models import DealDetails


class TestExtractDealDetails:
    """Tests for the extract_deal_details function."""

    def test_extract_basic_deal_html(self) -> None:
        """Test extracting from basic deal HTML structure."""
        html = """
        <html>
        <head><title>Wine Deal</title></head>
        <body>
            <h1 class="product-title">Château Margaux 2015</h1>
            <div class="pricing">
                <span class="retail-price">Retail: $1,200.00</span>
                <span class="best-web">Best Web: $999.00</span>
                <span class="last-bottle-price">Last Bottle: $849.99</span>
            </div>
            <div class="details">
                <span class="vintage">2015</span>
                <span class="size">750ml</span>
            </div>
        </body>
        </html>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Château Margaux 2015"
        assert result.vintage == 2015
        assert result.bottle_size_ml == 750
        assert result.deal_price == 849.99

    def test_extract_magnum_bottle(self) -> None:
        """Test extracting magnum bottle size."""
        html = """
        <html>
        <body>
            <h1>Dom Pérignon Champagne Magnum</h1>
            <p>Size: 1.5L Magnum</p>
            <div class="price">Last Bottle Deal: $299.95</div>
        </body>
        </html>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Dom Pérignon Champagne Magnum"
        assert result.vintage is None
        assert result.bottle_size_ml == 1500
        assert result.deal_price == 299.95

    def test_extract_half_bottle(self) -> None:
        """Test extracting half bottle (375ml)."""
        html = """
        <div>
            <h2 class="wine-title">Sauternes Dessert Wine 2018</h2>
            <p>Vintage 2018 in 375ml half bottles</p>
            <span class="deal-price">$45.50</span>
            <span class="retail">Retail $65.00</span>
        </div>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Sauternes Dessert Wine 2018"
        assert result.vintage == 2018
        assert result.bottle_size_ml == 375
        assert result.deal_price == 45.50

    def test_extract_no_vintage(self) -> None:
        """Test extracting wine without vintage."""
        html = """
        <html>
        <body>
            <h1>Everyday Red Blend NV</h1>
            <div>Non-vintage blend</div>
            <div class="current-price">$18.99</div>
        </body>
        </html>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Everyday Red Blend NV"
        assert result.vintage is None
        assert result.bottle_size_ml == 750  # Default
        assert result.deal_price == 18.99

    def test_extract_with_complex_pricing(self) -> None:
        """Test extracting when there are multiple prices but we want LastBottle only."""
        html = """
        <div class="wine-detail">
            <h1 class="title">Barolo Riserva 2017</h1>
            <div class="pricing-section">
                <div>Retail Price: $89.99</div>
                <div>Best Web Price: $75.00</div>
                <div>Our Last Bottle Special: $62.50</div>
            </div>
            <p>Vintage: 2017, Size: Standard 750ml</p>
        </div>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Barolo Riserva 2017"
        assert result.vintage == 2017
        assert result.bottle_size_ml == 750
        assert result.deal_price == 62.50

    def test_extract_large_format(self) -> None:
        """Test extracting large format bottles."""
        html = """
        <article>
            <h1>Bordeaux Blend Double Magnum</h1>
            <div class="specifications">
                <span>Year: 2019</span>
                <span>Format: 3L Double Magnum</span>
            </div>
            <div class="offer">Last Bottle Price $450.00</div>
        </article>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Bordeaux Blend Double Magnum"
        assert result.vintage == 2019
        assert result.bottle_size_ml == 3000
        assert result.deal_price == 450.00

    def test_extract_with_comma_price(self) -> None:
        """Test extracting price with comma formatting."""
        html = """
        <div>
            <h1>Rare Vintage Port 1985</h1>
            <div class="deal">Last Bottle: $1,299.99</div>
            <div>Bottle size: 750ml</div>
        </div>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Rare Vintage Port 1985"
        assert result.vintage == 1985
        assert result.bottle_size_ml == 750
        assert result.deal_price == 1299.99

    def test_extract_split_bottle(self) -> None:
        """Test extracting split/piccolo size bottles."""
        html = """
        <section>
            <h2>Champagne Piccolo 2020</h2>
            <p>Perfect for individual servings - 187ml split bottles</p>
            <span class="sale-price">$12.75 each</span>
        </section>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Champagne Piccolo 2020"
        assert result.vintage == 2020
        assert result.bottle_size_ml == 187
        assert result.deal_price == 12.75

    def test_extract_fallback_headings(self) -> None:
        """Test fallback to different heading elements."""
        html = """
        <html>
        <body>
            <div class="header">
                <h3>Pinot Noir Reserve 2021</h3>
            </div>
            <div>
                <p>Size: 750ml standard</p>
                <p>Special offer: $39.95</p>
            </div>
        </body>
        </html>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Pinot Noir Reserve 2021"
        assert result.vintage == 2021
        assert result.bottle_size_ml == 750
        assert result.deal_price == 39.95

    def test_extract_imperial_bottle(self) -> None:
        """Test extracting Imperial size (6L) bottles."""
        html = """
        <div class="product">
            <h1 class="name">Burgundy Grand Cru Imperial</h1>
            <div class="vintage">Vintage: 2016</div>
            <div class="format">Imperial 6L Format</div>
            <div class="pricing">
                <div class="retail">Retail: $2,500</div>
                <div class="last-bottle">Last Bottle: $1,899.00</div>
            </div>
        </div>
        """

        result = extract_deal_details(html)
        assert result is not None
        assert result.wine_name == "Burgundy Grand Cru Imperial"
        assert result.vintage == 2016
        assert result.bottle_size_ml == 6000
        assert result.deal_price == 1899.00

    def test_extract_fails_no_wine_name(self) -> None:
        """Test that extraction fails when no wine name is found."""
        html = """
        <html>
        <body>
            <div>Some content without a proper wine name</div>
            <span class="price">$25.00</span>
        </body>
        </html>
        """

        result = extract_deal_details(html)
        assert result is None

    def test_extract_fails_no_price(self) -> None:
        """Test that extraction fails when no valid price is found."""
        html = """
        <html>
        <body>
            <h1>Great Wine Name 2020</h1>
            <div>Details about the wine</div>
            <span>No price information</span>
        </body>
        </html>
        """

        result = extract_deal_details(html)
        assert result is None

    def test_extract_ignores_retail_best_web(self) -> None:
        """Test that retail and best web prices are ignored."""
        html = """
        <div>
            <h1 class="product-name">Test Wine 2022</h1>
            <div class="pricing">
                <div class="retail-price">Retail: $100.00</div>
                <div class="best-web-price">Best Web: $85.00</div>
                <!-- No LastBottle price, should return None -->
            </div>
        </div>
        """

        result = extract_deal_details(html)
        assert result is None

    def test_extract_deal_price_patterns(self) -> None:
        """Test various deal price patterns."""
        test_cases = [
            ("Deal: $45.99", 45.99),
            ("Sale Price $32.50", 32.50),
            ("Special Offer: $78.00", 78.00),
            ("$25.99 Special", 25.99),
        ]

        for price_text, expected_price in test_cases:
            html = f"""
            <div>
                <h1>Test Wine</h1>
                <div>{price_text}</div>
            </div>
            """

            result = extract_deal_details(html)
            assert result is not None
            assert result.deal_price == expected_price

    def test_extract_vintage_edge_cases(self) -> None:
        """Test vintage extraction edge cases."""
        test_cases = [
            ("Wine from 1995", 1995),
            ("2023 Harvest", 2023),
            ("Made in 2010", 2010),
            ("Contains 1800 (not vintage)", None),  # Too old
            ("Contains 2050 (not vintage)", None),  # Too far in future
        ]

        for text, expected_vintage in test_cases:
            html = f"""
            <div>
                <h1>Test Wine</h1>
                <p>{text}</p>
                <span class="price">$30.00</span>
            </div>
            """

            result = extract_deal_details(html)
            assert result is not None
            assert result.vintage == expected_vintage


class TestDealDetailsModel:
    """Tests for the DealDetails model."""

    def test_deal_details_creation(self) -> None:
        """Test creating DealDetails instance."""
        details = DealDetails(
            wine_name="Test Wine",
            vintage=2020,
            bottle_size_ml=750,
            deal_price=45.99
        )

        assert details.wine_name == "Test Wine"
        assert details.vintage == 2020
        assert details.bottle_size_ml == 750
        assert details.deal_price == 45.99

    def test_deal_details_defaults(self) -> None:
        """Test DealDetails with default values."""
        details = DealDetails(
            wine_name="Another Wine",
            deal_price=25.50
        )

        assert details.wine_name == "Another Wine"
        assert details.vintage is None
        assert details.bottle_size_ml == 750  # Default
        assert details.deal_price == 25.50

    def test_deal_details_string_representation(self) -> None:
        """Test string representation of DealDetails."""
        # With vintage and standard size
        details1 = DealDetails(
            wine_name="Cabernet Sauvignon",
            vintage=2019,
            deal_price=35.99
        )
        assert str(details1) == "Cabernet Sauvignon 2019: $35.99"

        # With vintage and non-standard size
        details2 = DealDetails(
            wine_name="Champagne",
            vintage=2018,
            bottle_size_ml=1500,
            deal_price=125.00
        )
        assert str(details2) == "Champagne 2018 (1500ml): $125.00"

        # No vintage, standard size
        details3 = DealDetails(
            wine_name="House Red",
            deal_price=15.99
        )
        assert str(details3) == "House Red: $15.99"

    def test_deal_details_validation(self) -> None:
        """Test DealDetails validation."""
        # Valid instance
        details = DealDetails(
            wine_name="Valid Wine",
            deal_price=29.99
        )
        assert details.deal_price == 29.99

        # Invalid price (should raise validation error)
        with pytest.raises(ValueError):
            DealDetails(
                wine_name="Invalid Wine",
                deal_price=-5.00  # Negative price not allowed
            )

