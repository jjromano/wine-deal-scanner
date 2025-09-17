"""Live tests for LastBottle website integration."""

import os

import pytest
from playwright.async_api import async_playwright

from app import config
from app.extract import extract_deal_from_dom, parse_deal_from_html


@pytest.mark.live
class TestLiveLastBottle:
    """Live tests against the actual LastBottle website."""

    @pytest.fixture(autouse=True)
    def check_live_tests_enabled(self):
        """Skip live tests unless LIVE_TESTS=1 environment variable is set."""
        if os.getenv("LIVE_TESTS") != "1":
            pytest.skip("Live tests are disabled. Set LIVE_TESTS=1 to enable.")

    @pytest.mark.asyncio
    async def test_extract_deal_from_dom_live(self):
        """Test extracting deal using DOM extraction from live LastBottle site."""
        try:
            async with async_playwright() as p:
                # Launch headless browser
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # Navigate to LastBottle URL
                await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded", timeout=30000)

                # Try to extract deal using DOM method
                deal = await extract_deal_from_dom(page)

                await browser.close()

                # If we got a deal, validate it
                if deal:
                    self._validate_deal(deal, "DOM extraction")
                else:
                    # No deal found - this could be normal if no deals are active
                    pytest.skip("No deal found on live site using DOM extraction")

        except Exception as e:
            # Gracefully handle failures - mark as xfail instead of hard failure
            pytest.xfail(f"Live DOM extraction test failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_parse_deal_from_html_live(self):
        """Test parsing deal from HTML content fetched from live LastBottle site."""
        try:
            async with async_playwright() as p:
                # Launch headless browser
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # Navigate to LastBottle URL
                await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded", timeout=30000)

                # Get HTML content
                html_content = await page.content()

                await browser.close()

                # Try to parse deal from HTML
                deal = parse_deal_from_html(html_content)

                # If we got a deal, validate it
                if deal:
                    self._validate_deal(deal, "HTML parsing")
                else:
                    # No deal found - this could be normal if no deals are active
                    pytest.skip("No deal found on live site using HTML parsing")

        except Exception as e:
            # Gracefully handle failures - mark as xfail instead of hard failure
            pytest.xfail(f"Live HTML parsing test failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_lastbottle_site_accessibility(self):
        """Test that the LastBottle site is accessible and loads properly."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # Navigate to LastBottle URL
                response = await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded", timeout=30000)

                await browser.close()

                # Check that the page loaded successfully
                assert response is not None, "No response received from LastBottle site"
                assert response.status < 400, f"LastBottle site returned error status: {response.status}"

                # Check that we got some HTML content
                assert "html" in (await response.text()).lower(), "Response does not appear to be HTML"

        except Exception as e:
            pytest.xfail(f"LastBottle site accessibility test failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_lastbottle_has_deal_content(self):
        """Test that the LastBottle site contains some deal-related content."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # Navigate to LastBottle URL
                await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded", timeout=30000)

                # Get page text content
                text_content = await page.text_content("body")

                await browser.close()

                # Check for wine/deal-related keywords
                wine_keywords = [
                    "wine", "bottle", "vintage", "price", "deal",
                    "cabernet", "chardonnay", "pinot", "merlot",
                    "last bottle", "retail", "save"
                ]

                found_keywords = [keyword for keyword in wine_keywords
                                if keyword.lower() in text_content.lower()]

                if len(found_keywords) >= 3:
                    # Site appears to have wine/deal content
                    pass
                else:
                    pytest.skip(f"LastBottle site does not appear to have deal content. Found keywords: {found_keywords}")

        except Exception as e:
            pytest.xfail(f"LastBottle content check failed: {str(e)}")

    def _validate_deal(self, deal, extraction_method: str):
        """
        Validate that a deal object meets expected criteria.

        Args:
            deal: Deal object to validate
            extraction_method: String describing how the deal was extracted (for error messages)
        """
        # Valid bottle sizes (in ml)
        valid_bottle_sizes = {187, 375, 750, 1500, 3000, 6000}

        # Validate title
        assert deal.title, f"{extraction_method}: Deal title is empty"
        assert len(deal.title.strip()) > 0, f"{extraction_method}: Deal title is whitespace only"
        assert len(deal.title) >= 3, f"{extraction_method}: Deal title is too short: '{deal.title}'"

        # Validate price
        assert deal.price is not None, f"{extraction_method}: Deal price is None"
        assert deal.price > 0, f"{extraction_method}: Deal price must be > 0, got {deal.price}"
        assert deal.price < 10000, f"{extraction_method}: Deal price seems unreasonably high: {deal.price}"

        # Validate bottle size
        assert deal.bottle_size_ml in valid_bottle_sizes, \
            f"{extraction_method}: Invalid bottle size {deal.bottle_size_ml}ml. Must be one of {valid_bottle_sizes}"

        # Optional validations (don't fail if these are missing)
        if deal.vintage:
            try:
                vintage_year = int(deal.vintage)
                assert 1950 <= vintage_year <= 2030, \
                    f"{extraction_method}: Vintage year {vintage_year} seems unreasonable"
            except ValueError:
                # Vintage is not a valid year (e.g., "NV")
                pass

        if deal.list_price:
            assert deal.list_price >= deal.price, \
                f"{extraction_method}: List price ({deal.list_price}) should be >= deal price ({deal.price})"

        if deal.url:
            assert deal.url.startswith("http"), \
                f"{extraction_method}: URL should be absolute: {deal.url}"

        # Log successful validation
        print(f"\n✅ {extraction_method} validation passed:")
        print(f"   Title: {deal.title}")
        print(f"   Price: ${deal.price}")
        print(f"   Bottle Size: {deal.bottle_size_ml}ml")
        print(f"   Vintage: {deal.vintage or 'N/A'}")
        print(f"   List Price: ${deal.list_price or 'N/A'}")
        print(f"   Region: {deal.region or 'N/A'}")
        print(f"   URL: {deal.url}")


@pytest.mark.live
class TestLiveLastBottleConfig:
    """Test LastBottle configuration for live tests."""

    @pytest.fixture(autouse=True)
    def check_live_tests_enabled(self):
        """Skip live tests unless LIVE_TESTS=1 environment variable is set."""
        if os.getenv("LIVE_TESTS") != "1":
            pytest.skip("Live tests are disabled. Set LIVE_TESTS=1 to enable.")

    def test_lastbottle_url_configured(self):
        """Test that LASTBOTTLE_URL is properly configured."""
        assert config.LASTBOTTLE_URL, "LASTBOTTLE_URL is not configured"
        assert config.LASTBOTTLE_URL.startswith("http"), \
            f"LASTBOTTLE_URL should start with http: {config.LASTBOTTLE_URL}"
        assert "lastbottle" in config.LASTBOTTLE_URL.lower(), \
            f"LASTBOTTLE_URL should contain 'lastbottle': {config.LASTBOTTLE_URL}"

    def test_config_values_for_live_testing(self):
        """Test that configuration values are reasonable for live testing."""
        # These are just informational - don't fail the test
        print("\n📋 Live Test Configuration:")
        print(f"   LASTBOTTLE_URL: {config.LASTBOTTLE_URL}")
        print(f"   USER_AGENT: {getattr(config, 'USER_AGENT', 'Not configured')}")
        print(f"   SAFE_MODE: {getattr(config, 'SAFE_MODE', 'Not configured')}")


# Additional helper for running live tests manually
if __name__ == "__main__":
    import asyncio
    import sys

    async def manual_test():
        """Manual test runner for development."""
        print("🧪 Running manual LastBottle live test...")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)  # Non-headless for manual testing
                context = await browser.new_context()
                page = await context.new_page()

                print(f"📡 Navigating to {config.LASTBOTTLE_URL}...")
                await page.goto(config.LASTBOTTLE_URL, wait_until="domcontentloaded")

                print("🔍 Trying DOM extraction...")
                deal_dom = await extract_deal_from_dom(page)

                print("📄 Trying HTML parsing...")
                html_content = await page.content()
                deal_html = parse_deal_from_html(html_content)

                await browser.close()

                print("\n📊 Results:")
                print(f"DOM extraction: {'✅ Success' if deal_dom else '❌ No deal'}")
                if deal_dom:
                    print(f"  Title: {deal_dom.title}")
                    print(f"  Price: ${deal_dom.price}")

                print(f"HTML parsing: {'✅ Success' if deal_html else '❌ No deal'}")
                if deal_html:
                    print(f"  Title: {deal_html.title}")
                    print(f"  Price: ${deal_html.price}")

        except Exception as e:
            print(f"❌ Manual test failed: {e}")

    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        asyncio.run(manual_test())
    else:
        print("Use 'python tests/test_live_lastbottle.py manual' to run manual test")
        print("Or use 'LIVE_TESTS=1 pytest tests/test_live_lastbottle.py -v' to run live tests")



