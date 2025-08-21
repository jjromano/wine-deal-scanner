"""Tests for LastBottle HTML parser functionality."""

from pathlib import Path

import pytest

from app.extract import parse_deal_from_html
from app.models import Deal


class TestLastBottleParser:
    """Tests for the parse_deal_from_html function."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Get the fixtures directory path."""
        return Path(__file__).parent / "fixtures" / "lastbottle"

    @pytest.fixture
    def sample_deal_html(self, fixtures_dir: Path) -> str:
        """Load sample deal HTML fixture."""
        return (fixtures_dir / "sample_deal.html").read_text()

    @pytest.fixture
    def no_vintage_deal_html(self, fixtures_dir: Path) -> str:
        """Load no-vintage deal HTML fixture."""
        return (fixtures_dir / "sample_deal_no_vintage.html").read_text()

    def test_parse_complete_deal(self, sample_deal_html: str) -> None:
        """Test parsing a complete deal with all fields."""
        deal = parse_deal_from_html(sample_deal_html)

        assert deal is not None
        assert isinstance(deal, Deal)

        # Check wine name extraction
        assert deal.title == "Château Margaux 2015 Magnum 1.5L"

        # Check Last Bottle price is selected (not retail or best web)
        assert deal.price == 649.99

        # Check bottle size parsing (Magnum 1.5L -> 1500ml)
        assert deal.bottle_size_ml == 1500

        # Check vintage extraction
        assert deal.vintage == "2015"

        # Check URL canonicalization
        assert deal.url == "https://www.lastbottle.com/wine/chateau-margaux-2015-magnum"

        # Check optional fields
        assert deal.list_price == 899.99  # MSRP/retail price
        assert deal.region == "Margaux, Bordeaux"

    def test_parse_no_vintage_deal(self, no_vintage_deal_html: str) -> None:
        """Test parsing a deal without vintage."""
        deal = parse_deal_from_html(no_vintage_deal_html)

        assert deal is not None
        assert deal.title == "House Red Blend NV"
        assert deal.price == 14.99  # Last Bottle price
        assert deal.bottle_size_ml == 750  # Standard bottle
        assert deal.vintage is None  # No vintage
        assert deal.url == "https://www.lastbottle.com/wine/house-red-blend-nv"
        assert deal.list_price == 25.99  # Retail price
        assert deal.region == "California"

    def test_chooses_last_bottle_price_only(self) -> None:
        """Test that only Last Bottle price is selected, ignoring retail/best web."""
        html = '''
        <html>
        <body>
            <h1>Test Wine 2020</h1>
            <div class="pricing">
                <div>Retail Price: $100.00</div>
                <div>Best Web Price: $85.00</div>
                <div>Last Bottle Price: $69.99</div>
            </div>
        </body>
        </html>
        '''

        deal = parse_deal_from_html(html)

        assert deal is not None
        assert deal.price == 69.99  # Should pick Last Bottle price
        assert deal.title == "Test Wine 2020"

    def test_price_extraction_patterns(self) -> None:
        """Test various price extraction patterns for Last Bottle price."""
        test_cases = [
            # Different formats for Last Bottle price
            ('Last Bottle: $45.99', 45.99),
            ('Last Bottle Price: $67.50', 67.50),
            ('Our Last Bottle deal: $89.99', 89.99),
            ('LastBottle: $125.00', 125.00),
            ('Last bottle special: $33.33', 33.33),
        ]

        for price_text, expected_price in test_cases:
            html = f'''
            <html>
            <body>
                <h1>Test Wine</h1>
                <div class="pricing">
                    <div>Retail: $200.00</div>
                    <div>{price_text}</div>
                </div>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.price == expected_price, f"Failed for pattern: {price_text}"

    def test_bottle_size_parsing(self) -> None:
        """Test bottle size parsing to milliliters."""
        test_cases = [
            # Format in title -> expected ml
            ("Wine Name 375ml", 375),
            ("Wine Name 750ml", 750),
            ("Wine Name Magnum 1.5L", 1500),
            ("Wine Name Double Magnum 3L", 3000),
            ("Wine Name Split 187ml", 187),
            ("Wine Name Half Bottle 375ml", 375),
            ("Wine Name Standard 750ml", 750),
            ("Wine Name Imperial 6L", 6000),
            ("Wine Name No Size", 750),  # Default
        ]

        for title, expected_ml in test_cases:
            html = f'''
            <html>
            <body>
                <h1>{title}</h1>
                <div>Last Bottle: $50.00</div>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.bottle_size_ml == expected_ml, f"Failed for title: {title}"

    def test_vintage_extraction(self) -> None:
        """Test vintage extraction from various locations."""
        test_cases = [
            # HTML content -> expected vintage
            ('<h1>Wine Name 2018</h1>', "2018"),
            ('<h1>Wine Name</h1><span class="vintage">2020</span>', "2020"),
            ('<h1>Wine Name</h1><p>Vintage: 2019</p>', "2019"),
            ('<h1>Wine Name</h1><div>From 2021 vintage</div>', "2021"),
            ('<h1>Wine Name NV</h1>', None),  # No vintage
            ('<h1>Wine Name</h1>', None),  # No vintage mentioned
        ]

        for content, expected_vintage in test_cases:
            html = f'''
            <html>
            <body>
                {content}
                <div>Last Bottle: $50.00</div>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.vintage == expected_vintage, f"Failed for content: {content}"

    def test_url_extraction_and_canonicalization(self) -> None:
        """Test URL extraction and canonicalization."""
        test_cases = [
            # HTML with different URL patterns -> expected canonical URL
            (
                '<link rel="canonical" href="https://www.lastbottle.com/wine/test-wine">',
                "https://www.lastbottle.com/wine/test-wine"
            ),
            (
                '<meta property="og:url" content="https://www.lastbottle.com/deals/special-wine">',
                "https://www.lastbottle.com/deals/special-wine"
            ),
            (
                '<a href="/wine/relative-path" class="wine-link">Wine Link</a>',
                "https://www.lastbottle.com/wine/relative-path"
            ),
            (
                '<a href="wine/no-slash">Wine Link</a>',
                "https://www.lastbottle.com/wine/no-slash"
            ),
            (
                # No URL found -> fallback
                '<div>No URL here</div>',
                "https://www.lastbottle.com/wine/unknown"
            ),
        ]

        for url_html, expected_url in test_cases:
            html = f'''
            <html>
            <head>{url_html}</head>
            <body>
                <h1>Test Wine</h1>
                <div>Last Bottle: $50.00</div>
                {url_html}
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.url == expected_url, f"Failed for URL HTML: {url_html}"

    def test_region_extraction(self) -> None:
        """Test region/appellation extraction."""
        test_cases = [
            # Content -> expected region
            ("From Napa Valley", "Napa Valley"),
            ("Region: Sonoma Valley", "Sonoma Valley"),
            ("Appellation: Bordeaux", "Bordeaux"),
            ("From Burgundy, France", "Burgundy, France"),
            ("Champagne region wine", "Champagne"),
            ("Tuscany hills vineyard", "Tuscany"),
            ("Barossa Valley estate", "Barossa Valley"),
            ("No region mentioned", None),
        ]

        for content, expected_region in test_cases:
            html = f'''
            <html>
            <body>
                <h1>Test Wine</h1>
                <div>Last Bottle: $50.00</div>
                <p>{content}</p>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.region == expected_region, f"Failed for content: {content}"

    def test_list_price_extraction(self) -> None:
        """Test retail/MSRP/list price extraction."""
        test_cases = [
            # Content -> expected list price
            ("Retail: $89.99", 89.99),
            ("MSRP: $125.00", 125.00),
            ("List Price: $67.50", 67.50),
            ("Was: $99.99", 99.99),
            ("Retail Price: $1,250.00", 1250.00),  # With comma
            ("No retail price", None),
        ]

        for content, expected_list_price in test_cases:
            html = f'''
            <html>
            <body>
                <h1>Test Wine</h1>
                <div>Last Bottle: $50.00</div>
                <p>{content}</p>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.list_price == expected_list_price, f"Failed for content: {content}"

    def test_ignores_retail_and_best_web_prices(self) -> None:
        """Test that retail and best web prices are ignored for deal price."""
        html = '''
        <html>
        <body>
            <h1>Test Wine 2020</h1>
            <div class="pricing">
                <div class="retail-price">Retail Price: $150.00</div>
                <div class="best-web-price">Best Web Price: $120.00</div>
                <div class="other-price">Some Other Price: $90.00</div>
                <div class="last-bottle-price">Last Bottle: $75.99</div>
            </div>
        </body>
        </html>
        '''

        deal = parse_deal_from_html(html)

        assert deal is not None
        assert deal.price == 75.99  # Should only use Last Bottle price
        assert deal.list_price == 150.00  # Should extract retail as list price

    def test_price_element_selectors(self) -> None:
        """Test price extraction from specific CSS selectors."""
        test_cases = [
            ('.deal-price', 'deal-price'),
            ('.last-bottle-price', 'last-bottle-price'),
            ('.lastbottle-price', 'lastbottle-price'),
            ('.sale-price', 'sale-price'),
            ('.current-price', 'current-price'),
            ('.price', 'price'),
        ]

        for selector, class_name in test_cases:
            html = f'''
            <html>
            <body>
                <h1>Test Wine</h1>
                <div class="{class_name}">$89.99</div>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.price == 89.99, f"Failed for selector: {selector}"

    def test_empty_or_invalid_html(self) -> None:
        """Test handling of empty or invalid HTML."""
        test_cases = [
            "",  # Empty string
            "<html></html>",  # Empty HTML
            "<html><body></body></html>",  # No content
            "<html><body><h1></h1></body></html>",  # Empty title
            "<html><body><h1>Wine</h1></body></html>",  # No price
            "Invalid HTML content",  # Not HTML
        ]

        for html in test_cases:
            deal = parse_deal_from_html(html)
            assert deal is None, f"Should return None for: {html[:50]}..."

    def test_wine_name_extraction_selectors(self) -> None:
        """Test wine name extraction from various selectors."""
        test_cases = [
            ('<h1 class="wine-name">Selector Wine</h1>', "Selector Wine"),
            ('<h1 class="product-title">Product Wine</h1>', "Product Wine"),
            ('<h1 class="deal-title">Deal Wine</h1>', "Deal Wine"),
            ('<div class="wine-title">Div Wine</div>', "Div Wine"),
            ('<span class="product-name">Span Wine</span>', "Span Wine"),
            ('<h1>Generic H1 Wine</h1>', "Generic H1 Wine"),
            ('<h2 class="title">H2 Title Wine</h2>', "H2 Title Wine"),
        ]

        for name_html, expected_name in test_cases:
            html = f'''
            <html>
            <body>
                {name_html}
                <div>Last Bottle: $50.00</div>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.title == expected_name, f"Failed for HTML: {name_html}"

    def test_complex_pricing_scenario(self) -> None:
        """Test complex pricing scenario with multiple price mentions."""
        html = '''
        <html>
        <body>
            <h1>Complex Wine 2019 Magnum 1.5L</h1>
            <div class="wine-info">
                <p>From Napa Valley, California</p>
                <p>Vintage: 2019</p>
                <p>Format: Magnum (1.5 Liters)</p>
            </div>

            <div class="pricing-section">
                <div class="price-comparison">
                    <div class="retail">Retail Price: $299.99</div>
                    <div class="competitor">Best Web Price: $249.99</div>
                    <div class="our-deal">
                        <strong>Last Bottle Special: $199.99</strong>
                        <span>Save $100!</span>
                    </div>
                </div>
                <p>MSRP: $299.99</p>
                <p>Our Last Bottle price: $199.99 (limited quantity)</p>
            </div>

            <div class="description">
                <p>Exceptional wine from 2019 vintage in Magnum format.</p>
            </div>
        </body>
        </html>
        '''

        deal = parse_deal_from_html(html)

        assert deal is not None
        assert deal.title == "Complex Wine 2019 Magnum 1.5L"
        assert deal.price == 199.99  # Last Bottle price
        assert deal.list_price == 299.99  # MSRP/Retail
        assert deal.vintage == "2019"
        assert deal.bottle_size_ml == 1500  # Magnum
        assert deal.region == "Napa Valley"
        assert deal.url == "https://www.lastbottle.com/wine/unknown"  # Fallback URL


class TestLastBottleParserIntegration:
    """Integration tests for the LastBottle parser."""

    def test_realistic_deal_page_structure(self) -> None:
        """Test parsing a realistic deal page structure."""
        html = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Dom Pérignon Vintage 2012 - LastBottle</title>
            <link rel="canonical" href="https://www.lastbottle.com/wine/dom-perignon-2012">
            <meta property="og:url" content="https://www.lastbottle.com/wine/dom-perignon-2012">
        </head>
        <body>
            <header>
                <nav><a href="/">LastBottle</a></nav>
            </header>

            <main class="wine-page">
                <h1 class="wine-name">Dom Pérignon Vintage 2012</h1>

                <div class="wine-details">
                    <div class="vintage">2012</div>
                    <div class="region">Champagne, France</div>
                    <div class="size">750ml</div>
                </div>

                <div class="pricing">
                    <div class="retail-price">Retail: $189.99</div>
                    <div class="best-web">Best Web: $169.99</div>
                    <div class="last-bottle-price">Last Bottle: $149.99</div>
                </div>

                <div class="purchase">
                    <button>Buy Now - $149.99</button>
                </div>
            </main>
        </body>
        </html>
        '''

        deal = parse_deal_from_html(html)

        assert deal is not None
        assert deal.title == "Dom Pérignon Vintage 2012"
        assert deal.price == 149.99
        assert deal.list_price == 189.99
        assert deal.vintage == "2012"
        assert deal.bottle_size_ml == 750
        assert deal.region == "Champagne"
        assert deal.url == "https://www.lastbottle.com/wine/dom-perignon-2012"

    def test_minimal_valid_deal_page(self) -> None:
        """Test parsing minimal valid deal page."""
        html = '''
        <html>
        <body>
            <h1>Simple Wine</h1>
            <div>Last Bottle: $25.99</div>
        </body>
        </html>
        '''

        deal = parse_deal_from_html(html)

        assert deal is not None
        assert deal.title == "Simple Wine"
        assert deal.price == 25.99
        assert deal.vintage is None
        assert deal.bottle_size_ml == 750  # Default
        assert deal.region is None
        assert deal.list_price is None
        assert deal.url == "https://www.lastbottle.com/wine/unknown"  # Fallback

    def test_edge_case_price_formats(self) -> None:
        """Test edge case price formats."""
        test_cases = [
            ("Last Bottle: $1,299.99", 1299.99),  # Comma in price
            ("Last bottle deal $45", 45.0),  # No decimal
            ("Last Bottle Price: $89.00", 89.0),  # Zero cents
            ("Our Last Bottle special: $33.33", 33.33),  # Repeating digits
        ]

        for price_text, expected_price in test_cases:
            html = f'''
            <html>
            <body>
                <h1>Edge Case Wine</h1>
                <div>{price_text}</div>
            </body>
            </html>
            '''

            deal = parse_deal_from_html(html)
            assert deal is not None
            assert deal.price == expected_price, f"Failed for: {price_text}"
