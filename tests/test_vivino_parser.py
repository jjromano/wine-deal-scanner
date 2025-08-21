"""Tests for Vivino parser functionality."""

import pytest
from pathlib import Path

from app.vivino import parse_vivino_page


class TestVivinoParser:
    """Tests for the pure parser function parse_vivino_page."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Get the fixtures directory path."""
        return Path(__file__).parent / "fixtures" / "vivino"

    @pytest.fixture
    def wine_with_full_data_html(self, fixtures_dir: Path) -> str:
        """Load HTML fixture with complete wine data."""
        return (fixtures_dir / "wine_with_full_data.html").read_text()

    @pytest.fixture
    def wine_with_partial_data_html(self, fixtures_dir: Path) -> str:
        """Load HTML fixture with partial wine data."""
        return (fixtures_dir / "wine_with_partial_data.html").read_text()

    def test_parse_full_data(self, wine_with_full_data_html: str) -> None:
        """Test parsing HTML with complete wine data."""
        rating, rating_count, avg_price = parse_vivino_page(wine_with_full_data_html)

        assert rating == 4.5
        assert rating_count == 1247
        assert avg_price == 425.99

    def test_parse_partial_data(self, wine_with_partial_data_html: str) -> None:
        """Test parsing HTML with partial wine data (no price)."""
        rating, rating_count, avg_price = parse_vivino_page(wine_with_partial_data_html)

        assert rating == 3.8
        assert rating_count == 89
        assert avg_price is None

    def test_parse_empty_html(self) -> None:
        """Test parsing empty or invalid HTML."""
        rating, rating_count, avg_price = parse_vivino_page("")

        assert rating is None
        assert rating_count is None
        assert avg_price is None

    def test_parse_html_no_wine_data(self) -> None:
        """Test parsing HTML without wine data."""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Not a wine page</title></head>
        <body><p>This is not a wine page.</p></body>
        </html>
        """
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating is None
        assert rating_count is None
        assert avg_price is None

    def test_parse_json_ld_rating(self) -> None:
        """Test parsing rating from JSON-LD structured data."""
        html = '''
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "4.2",
                "reviewCount": "856"
            }
        }
        </script>
        </head>
        <body></body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 4.2
        assert rating_count == 856
        assert avg_price is None

    def test_parse_meta_property_rating(self) -> None:
        """Test parsing rating from meta properties."""
        html = '''
        <html>
        <head>
        <meta property="vivino:rating" content="3.9">
        <meta property="vivino:rating_count" content="234">
        <meta property="vivino:price" content="$67.50">
        </head>
        <body></body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 3.9
        assert rating_count == 234
        assert avg_price == 67.50

    def test_parse_data_attributes(self) -> None:
        """Test parsing from data attributes."""
        html = '''
        <html>
        <body>
        <div data-rating="4.7" data-price="$125.00">Wine info</div>
        <span>1,500 ratings</span>
        </body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 4.7
        assert rating_count == 1500
        assert avg_price == 125.00

    def test_parse_text_based_patterns(self) -> None:
        """Test parsing from text-based patterns."""
        html = '''
        <html>
        <body>
        <p>This wine has 542 reviews and an average price: $89.99</p>
        <div>Rating: 4.1 stars</div>
        </body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating is None  # No matching pattern for "4.1 stars"
        assert rating_count == 542
        assert avg_price == 89.99

    def test_parse_comma_separated_numbers(self) -> None:
        """Test parsing numbers with comma separators."""
        html = '''
        <html>
        <body>
        <div data-rating="4.6">
        <span>2,847 ratings</span>
        <p>Price: $1,250.00</p>
        </div>
        </body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 4.6
        assert rating_count == 2847
        assert avg_price == 1250.00

    def test_parse_multiple_price_patterns(self) -> None:
        """Test parsing different price patterns."""
        test_cases = [
            ('data-price="45.99"', 45.99),
            ('data-price="$78.50"', 78.50),
            ('"price": "125.00"', 125.00),
            ('"price": "$99.99"', 99.99),
            ('Average price: $67.89', 67.89),
            ('Price: 156.78', 156.78),
        ]

        for price_pattern, expected_price in test_cases:
            html = f'<html><body><div>{price_pattern}</div></body></html>'
            _, _, avg_price = parse_vivino_page(html)
            assert avg_price == expected_price, f"Failed for pattern: {price_pattern}"

    def test_parse_multiple_rating_count_patterns(self) -> None:
        """Test parsing different rating count patterns."""
        test_cases = [
            ('"reviewCount": 456', 456),
            ('content="789"', 789),  # meta property
            ('1,234 ratings', 1234),
            ('567 reviews', 567),
            ('2,890 Ratings', 2890),  # Case insensitive
        ]

        for count_pattern, expected_count in test_cases:
            html = f'<html><body><div>{count_pattern}</div></body></html>'
            if 'content=' in count_pattern:
                html = f'<html><head><meta property="vivino:rating_count" {count_pattern}></head><body></body></html>'
            elif 'reviewCount' in count_pattern:
                html = f'<html><head><script type="application/ld+json">{{{count_pattern}}}</script></head><body></body></html>'
            
            _, rating_count, _ = parse_vivino_page(html)
            assert rating_count == expected_count, f"Failed for pattern: {count_pattern}"

    def test_parse_invalid_numbers(self) -> None:
        """Test handling of invalid number formats."""
        html = '''
        <html>
        <body>
        <div data-rating="invalid">
        <span>not-a-number ratings</span>
        <p>Price: $invalid.price</p>
        </div>
        </body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        # Should handle invalid numbers gracefully
        assert rating is None
        assert rating_count is None
        assert avg_price is None

    def test_parse_edge_case_values(self) -> None:
        """Test parsing edge case values."""
        html = '''
        <html>
        <head>
        <meta property="vivino:rating" content="0.0">
        <meta property="vivino:rating_count" content="0">
        <meta property="vivino:price" content="$0.00">
        </head>
        <body></body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 0.0
        assert rating_count == 0
        assert avg_price == 0.0

    def test_parse_high_precision_values(self) -> None:
        """Test parsing high precision decimal values."""
        html = '''
        <html>
        <head>
        <script type="application/ld+json">
        {
            "aggregateRating": {
                "ratingValue": "4.567",
                "reviewCount": "12345"
            },
            "price": "123.456"
        }
        </script>
        </head>
        <body></body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 4.567
        assert rating_count == 12345
        assert avg_price == 123.456

    def test_parse_priority_order(self) -> None:
        """Test that parser follows the correct priority order for patterns."""
        # JSON-LD should take priority over meta properties
        html = '''
        <html>
        <head>
        <meta property="vivino:rating" content="3.0">
        <script type="application/ld+json">
        {
            "aggregateRating": {
                "ratingValue": "4.5"
            }
        }
        </script>
        </head>
        <body></body>
        </html>
        '''
        rating, _, _ = parse_vivino_page(html)

        # Should prefer JSON-LD value (4.5) over meta property (3.0)
        assert rating == 4.5


class TestVivinoParserIntegration:
    """Integration tests for the parser with realistic scenarios."""

    def test_parse_realistic_wine_page(self) -> None:
        """Test parsing a realistic wine page structure."""
        html = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Dom Pérignon Vintage 2012 - Vivino</title>
            <meta property="og:title" content="Dom Pérignon Vintage 2012">
            <meta property="vivino:rating" content="4.3">
            <meta property="vivino:rating_count" content="1856">
            <meta property="vivino:price" content="$189.99">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Dom Pérignon Vintage 2012",
                "brand": "Dom Pérignon",
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": "4.3",
                    "reviewCount": "1856",
                    "bestRating": "5",
                    "worstRating": "1"
                },
                "offers": {
                    "@type": "Offer",
                    "price": "189.99",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock"
                }
            }
            </script>
        </head>
        <body>
            <div class="wine-header">
                <h1>Dom Pérignon Vintage 2012</h1>
                <div class="wine-rating">
                    <span class="rating-value">4.3</span>
                    <span class="rating-count">1,856 ratings</span>
                </div>
            </div>
            <div class="wine-pricing">
                <span class="price-label">Average price: $189.99</span>
            </div>
        </body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 4.3
        assert rating_count == 1856
        assert avg_price == 189.99

    def test_parse_wine_without_structured_data(self) -> None:
        """Test parsing wine page without JSON-LD structured data."""
        html = '''
        <html>
        <head>
            <title>Simple Wine Page</title>
        </head>
        <body>
            <div class="wine-info" data-rating="3.7" data-price="45.50">
                <h1>Simple Red Wine 2020</h1>
                <p>This wine has 234 reviews from our community.</p>
                <div class="price">Price: $45.50</div>
            </div>
        </body>
        </html>
        '''
        rating, rating_count, avg_price = parse_vivino_page(html)

        assert rating == 3.7
        assert rating_count == 234
        assert avg_price == 45.50
