"""Tests for deal extraction functionality."""


from app.extract import deal_key, extract_deal_from_json, pick_lastbottle_price


class TestDealKey:
    """Tests for the deal_key function."""

    def test_basic_deal_key(self) -> None:
        """Test basic deal key generation."""
        key = deal_key("Cabernet Sauvignon", "2020", 25.99)
        assert key == "cabernet sauvignon|2020|25.99"

    def test_deal_key_no_vintage(self) -> None:
        """Test deal key with no vintage."""
        key = deal_key("Pinot Noir", None, 35.50)
        assert key == "pinot noir|unknown|35.50"

    def test_deal_key_normalization(self) -> None:
        """Test title normalization in deal key."""
        key = deal_key("Dom Pérignon Champagne!", "2015", 199.99)
        assert key == "dom perignon champagne|2015|199.99"

    def test_deal_key_whitespace_handling(self) -> None:
        """Test whitespace normalization."""
        key = deal_key("  Château   Margaux   ", "2010", 500.00)
        assert key == "chateau margaux|2010|500.00"

    def test_deal_key_price_formatting(self) -> None:
        """Test price formatting consistency."""
        key1 = deal_key("Wine", "2020", 10.0)
        key2 = deal_key("Wine", "2020", 10.00)
        assert key1 == key2 == "wine|2020|10.00"


class TestExtractDealFromJson:
    """Tests for the extract_deal_from_json function."""

    def test_extract_basic_deal(self) -> None:
        """Test extracting a basic deal from JSON."""
        json_data = {
            "name": "Cabernet Sauvignon Reserve",
            "price": 29.99,
            "url": "https://example.com/deal/123",
            "vintage": "2020",
            "region": "Napa Valley"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.title == "Cabernet Sauvignon Reserve"
        assert deal.price == 29.99
        assert deal.url == "https://example.com/deal/123"
        assert deal.vintage == "2020"
        assert deal.region == "Napa Valley"
        assert deal.list_price is None

    def test_extract_deal_with_list_price(self) -> None:
        """Test extracting deal with list price."""
        json_data = {
            "title": "Premium Bordeaux",
            "sale_price": 45.00,
            "list_price": 60.00,
            "product_url": "https://example.com/wine/456"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.title == "Premium Bordeaux"
        assert deal.price == 45.00
        assert deal.list_price == 60.00
        assert deal.url == "https://example.com/wine/456"

    def test_extract_deal_string_price(self) -> None:
        """Test extracting deal with string price."""
        json_data = {
            "product_name": "Chardonnay Special",
            "price": "$24.95",
            "link": "https://example.com/special"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.title == "Chardonnay Special"
        assert deal.price == 24.95
        assert deal.url == "https://example.com/special"

    def test_extract_deal_price_with_commas(self) -> None:
        """Test extracting deal with comma-formatted price."""
        json_data = {
            "name": "Expensive Vintage",
            "current_price": "1,299.99",
            "url": "https://example.com/expensive"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.price == 1299.99

    def test_extract_deal_missing_required_fields(self) -> None:
        """Test extraction fails with missing required fields."""
        # Missing price
        json_data = {
            "name": "Wine Without Price",
            "url": "https://example.com/noprice"
        }
        assert extract_deal_from_json(json_data) is None

        # Missing name
        json_data = {
            "price": 25.99,
            "url": "https://example.com/noname"
        }
        assert extract_deal_from_json(json_data) is None

        # Missing URL
        json_data = {
            "name": "Wine Without URL",
            "price": 25.99
        }
        assert extract_deal_from_json(json_data) is None

    def test_extract_deal_invalid_price(self) -> None:
        """Test extraction fails with invalid price."""
        json_data = {
            "name": "Invalid Price Wine",
            "price": "not a price",
            "url": "https://example.com/invalid"
        }
        assert extract_deal_from_json(json_data) is None

    def test_extract_deal_numeric_vintage(self) -> None:
        """Test extraction with numeric vintage."""
        json_data = {
            "name": "Vintage Wine",
            "price": 35.00,
            "url": "https://example.com/vintage",
            "year": 2018
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.vintage == "2018"

    def test_extract_deal_alternative_field_names(self) -> None:
        """Test extraction with alternative field names."""
        json_data = {
            "title": "Alternative Fields Wine",
            "current_price": 42.50,
            "original_price": 55.00,
            "product_url": "https://example.com/alt",
            "appellation": "Burgundy"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.title == "Alternative Fields Wine"
        assert deal.price == 42.50
        assert deal.list_price == 55.00
        assert deal.region == "Burgundy"

    def test_extract_deal_with_bottle_size(self) -> None:
        """Test extraction with bottle size detection."""
        json_data = {
            "name": "Champagne Magnum 1.5L Special",
            "price": 89.99,
            "url": "https://example.com/magnum",
            "size": "1500ml"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.title == "Champagne Magnum 1.5L Special"
        assert deal.bottle_size_ml == 1500  # Should detect magnum size

    def test_extract_deal_default_bottle_size(self) -> None:
        """Test extraction defaults to 750ml when no size detected."""
        json_data = {
            "name": "Standard Wine Bottle",
            "price": 25.99,
            "url": "https://example.com/standard"
        }

        deal = extract_deal_from_json(json_data)
        assert deal is not None
        assert deal.bottle_size_ml == 750  # Should default to standard size


# Mock payload for testing realistic data structure
MOCK_LASTBOTTLE_PAYLOAD = {
    "success": True,
    "data": {
        "deals": [
            {
                "id": 123,
                "wine_name": "Château Margaux 2015",
                "sale_price": 899.99,
                "retail_price": 1200.00,
                "vintage": "2015",
                "region": "Bordeaux, France",
                "product_url": "https://lastbottle.com/deals/chateau-margaux-2015",
                "description": "Premier Grand Cru Classé",
                "inventory": 6
            },
            {
                "id": 124,
                "wine_name": "Opus One 2018",
                "sale_price": 425.00,
                "retail_price": 500.00,
                "vintage": "2018",
                "region": "Napa Valley, California",
                "product_url": "https://lastbottle.com/deals/opus-one-2018",
                "description": "Bordeaux-style blend",
                "inventory": 3
            }
        ]
    }
}


def test_extract_from_mock_payload() -> None:
    """Test extraction from a realistic mock payload."""
    # Test extracting from the first deal in the array
    first_deal_data = MOCK_LASTBOTTLE_PAYLOAD["data"]["deals"][0]

    # Map to expected field names for our extraction function
    mapped_data = {
        "name": first_deal_data["wine_name"],
        "price": first_deal_data["sale_price"],
        "list_price": first_deal_data["retail_price"],
        "vintage": first_deal_data["vintage"],
        "region": first_deal_data["region"],
        "url": first_deal_data["product_url"]
    }

    deal = extract_deal_from_json(mapped_data)
    assert deal is not None
    assert deal.title == "Château Margaux 2015"
    assert deal.price == 899.99
    assert deal.list_price == 1200.00
    assert deal.vintage == "2015"
    assert deal.region == "Bordeaux, France"
    assert deal.url == "https://lastbottle.com/deals/chateau-margaux-2015"


class TestPickLastBottlePrice:
    """Tests for the pick_lastbottle_price function."""

    def test_pick_lastbottle_price_dict_variants(self) -> None:
        """Test extracting LastBottle price from nested dict structure."""
        payload = {
            "prices": {"retail": 75, "best_web": 49, "last_bottle": 39}
        }
        assert pick_lastbottle_price(payload) == 39.0

    def test_pick_lastbottle_price_flat_keys_and_text(self) -> None:
        """Test extracting LastBottle price from flat keys and HTML text."""
        # Test flat keys
        payload = {"retailPrice": "$70", "bestWebPrice": "$45", "lastBottlePrice": "$33"}
        assert pick_lastbottle_price(payload) == 33.0

        # Test HTML text
        html = "<div>Retail $85 • Best Web $55 • <strong>Last Bottle $41</strong></div>"
        assert pick_lastbottle_price(html) == 41.0

    def test_pick_lastbottle_price_ignores_retail_and_best_web(self) -> None:
        """Test that retail and best web prices are ignored when no LastBottle price."""
        # Should return None when only retail/best web prices are present
        payload = {"retail": 75, "best_web": 49, "store_price": 52}
        assert pick_lastbottle_price(payload) is None

        # Should return None for text without 'last bottle' mention
        text = "Retail $75, Best Web $49, Store $52"
        assert pick_lastbottle_price(text) is None

    def test_pick_lastbottle_price_various_key_formats(self) -> None:
        """Test various LastBottle key formats."""
        test_cases = [
            ({"last_bottle": 25.99}, 25.99),
            ({"lastBottle": "29.95"}, 29.95),
            ({"lastBottlePrice": "$35.50"}, 35.50),
            ({"last_bottle_price": 42.00}, 42.00),
            ({"lb": "48.99"}, 48.99),
        ]

        for payload, expected in test_cases:
            assert pick_lastbottle_price(payload) == expected

    def test_pick_lastbottle_price_nested_structures(self) -> None:
        """Test nested price structures."""
        # Test pricing nested object
        payload = {
            "pricing": {"retail": 85, "lastBottle": 55},
            "other_data": "ignored"
        }
        assert pick_lastbottle_price(payload) == 55.0

        # Test priceInfo nested object
        payload = {
            "priceInfo": {"msrp": 100, "last_bottle_price": 65},
        }
        assert pick_lastbottle_price(payload) == 65.0

    def test_pick_lastbottle_price_text_patterns(self) -> None:
        """Test text pattern matching for LastBottle prices."""
        test_cases = [
            ("Last bottle price is $29.99", 29.99),
            ("LAST BOTTLE: $45.50", 45.50),
            ("Our last bottle deal: €35.00", 35.00),
            ("Last Bottle £28.75", 28.75),
            ("Final last bottle offer $52.25", 52.25),
        ]

        for text, expected in test_cases:
            result = pick_lastbottle_price(text)
            assert result == expected, f"Failed for text: {text}"

    def test_pick_lastbottle_price_invalid_inputs(self) -> None:
        """Test invalid inputs return None."""
        assert pick_lastbottle_price(None) is None
        assert pick_lastbottle_price({}) is None
        assert pick_lastbottle_price("") is None
        assert pick_lastbottle_price(123) is None  # Non-dict, non-string
        assert pick_lastbottle_price({"invalid": "data"}) is None
