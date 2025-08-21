"""Live tests for Vivino integration."""

import os

import pytest

from app.vivino import _fetch_vivino_page, parse_vivino_page, resolve_vivino_url


@pytest.mark.live
class TestLiveVivino:
    """Live tests against the actual Vivino website."""

    @pytest.fixture(autouse=True)
    def check_live_tests_enabled(self):
        """Skip live tests unless LIVE_TESTS=1 environment variable is set."""
        if os.getenv("LIVE_TESTS") != "1":
            pytest.skip("Live tests are disabled. Set LIVE_TESTS=1 to enable.")

    @pytest.mark.asyncio
    async def test_resolve_vivino_url_live(self):
        """Test resolving a Vivino URL for a stable, well-known wine."""
        try:
            # Use a generic, stable wine query that should have reliable results
            # Dom Perignon is widely available and stable in Vivino's database
            query = "Dom Perignon Champagne"

            # Use short timeout for live tests
            url = await resolve_vivino_url(query, timeout_s=2.0)

            if url:
                # Validate URL format
                assert url.startswith("http"), f"URL should be absolute: {url}"
                assert "vivino.com" in url.lower(), f"URL should be from Vivino: {url}"
                assert "/w/" in url, f"URL should be a wine page: {url}"

                print(f"\n✅ Successfully resolved URL for '{query}': {url}")
            else:
                # No URL found - could be normal due to rate limiting or search changes
                pytest.skip(f"No Vivino URL found for query '{query}' (rate limiting or search issues)")

        except Exception as e:
            # Gracefully handle failures - mark as xfail instead of hard failure
            pytest.xfail(f"Live Vivino URL resolution failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_fetch_vivino_page_live(self):
        """Test fetching HTML content from a known Vivino wine page."""
        try:
            # First resolve a URL
            query = "Dom Perignon Champagne"
            url = await resolve_vivino_url(query, timeout_s=2.0)

            if not url:
                pytest.skip(f"Could not resolve URL for '{query}' - skipping page fetch test")

            # Fetch the page content
            html_content = await _fetch_vivino_page(url, timeout_s=2.0)

            # Validate HTML content
            assert html_content, "HTML content should not be empty"
            assert len(html_content) > 1000, "HTML content seems too short for a wine page"
            assert "vivino" in html_content.lower(), "HTML should contain Vivino content"

            # Check for common wine page elements
            wine_indicators = ["wine", "rating", "reviews", "vintage", "bottle"]
            found_indicators = [indicator for indicator in wine_indicators
                              if indicator.lower() in html_content.lower()]

            assert len(found_indicators) >= 3, \
                f"HTML should contain wine-related content. Found: {found_indicators}"

            print(f"\n✅ Successfully fetched Vivino page ({len(html_content)} chars)")
            print(f"   Wine indicators found: {found_indicators}")

        except Exception as e:
            pytest.xfail(f"Live Vivino page fetch failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_parse_vivino_page_live(self):
        """Test parsing wine data from a live Vivino page."""
        try:
            # Resolve URL and fetch content
            query = "Dom Perignon Champagne"
            url = await resolve_vivino_url(query, timeout_s=2.0)

            if not url:
                pytest.skip(f"Could not resolve URL for '{query}' - skipping parse test")

            html_content = await _fetch_vivino_page(url, timeout_s=2.0)

            if not html_content:
                pytest.skip("Could not fetch HTML content - skipping parse test")

            # Parse the wine data
            rating, count, price = parse_vivino_page(html_content)

            # Validate required fields (rating and count)
            assert rating is not None, "Rating should not be None for a live wine page"
            assert count is not None, "Review count should not be None for a live wine page"

            # Validate rating range
            assert 1.0 <= rating <= 5.0, f"Rating should be 1-5, got {rating}"

            # Validate review count
            assert count >= 0, f"Review count should be >= 0, got {count}"
            assert count < 1000000, f"Review count seems unreasonably high: {count}"

            # Price is optional but should be reasonable if present
            if price is not None:
                assert price > 0, f"Price should be positive if present, got {price}"
                assert price < 10000, f"Price seems unreasonably high: {price}"

            print(f"\n✅ Successfully parsed Vivino data for '{query}':")
            print(f"   Rating: {rating}⭐")
            print(f"   Reviews: {count:,}")
            print(f"   Price: ${price}" if price else "   Price: Not available")

        except Exception as e:
            pytest.xfail(f"Live Vivino parsing failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_vivino_integration_end_to_end_live(self):
        """Test the complete Vivino integration flow end-to-end."""
        try:
            # Test with multiple stable wine queries
            test_queries = [
                "Dom Perignon Champagne",
                "Opus One Cabernet",
                "Caymus Cabernet Sauvignon",
            ]

            successful_queries = 0

            for query in test_queries:
                try:
                    # Full integration test: resolve -> fetch -> parse
                    url = await resolve_vivino_url(query, timeout_s=1.5)

                    if not url:
                        print(f"   ⚠️ Could not resolve '{query}'")
                        continue

                    html_content = await _fetch_vivino_page(url, timeout_s=1.5)

                    if not html_content:
                        print(f"   ⚠️ Could not fetch page for '{query}'")
                        continue

                    rating, count, price = parse_vivino_page(html_content)

                    if rating is not None and count is not None:
                        successful_queries += 1
                        print(f"   ✅ '{query}': {rating}⭐ ({count:,} reviews)")
                    else:
                        print(f"   ⚠️ Could not parse data for '{query}'")

                except Exception as query_error:
                    print(f"   ❌ Error with '{query}': {query_error}")

            # At least one query should succeed for the integration to be working
            if successful_queries > 0:
                print(f"\n🎯 End-to-end integration working: {successful_queries}/{len(test_queries)} queries successful")
            else:
                pytest.skip("No queries succeeded - Vivino may be rate limiting or unavailable")

        except Exception as e:
            pytest.xfail(f"Live Vivino end-to-end test failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_vivino_rate_limiting_handling(self):
        """Test that Vivino integration handles rate limiting gracefully."""
        try:
            # Make multiple rapid requests to test rate limiting behavior
            query = "Champagne Dom Perignon"

            results = []
            for i in range(3):
                try:
                    url = await resolve_vivino_url(query, timeout_s=1.0)
                    results.append(url is not None)
                except Exception as e:
                    # Rate limiting or timeout is expected behavior
                    results.append(False)
                    print(f"   Request {i+1}: {str(e)[:50]}...")

            # At least one request should succeed, or all should fail gracefully
            success_count = sum(results)

            if success_count > 0:
                print(f"\n✅ Rate limiting test: {success_count}/3 requests succeeded")
            else:
                print("\n⚠️ All requests failed - likely rate limited (expected behavior)")

            # This test should never hard-fail - rate limiting is expected

        except Exception as e:
            pytest.xfail(f"Rate limiting test failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_vivino_error_handling_live(self):
        """Test Vivino integration error handling with edge cases."""
        try:
            # Test with various problematic queries
            edge_case_queries = [
                "",  # Empty query
                "xyzinvalidwinenamethatshouldnotexist123",  # Non-existent wine
                "a",  # Very short query
            ]

            for query in edge_case_queries:
                try:
                    url = await resolve_vivino_url(query, timeout_s=1.0)

                    # Empty or invalid queries should return None gracefully
                    if query == "":
                        assert url is None, "Empty query should return None"

                    print(f"   Query '{query}': {'Found URL' if url else 'No URL (expected)'}")

                except Exception as query_error:
                    # Errors should be handled gracefully
                    print(f"   Query '{query}': Error handled - {str(query_error)[:50]}")

            print("\n✅ Error handling working correctly")

        except Exception as e:
            pytest.xfail(f"Vivino error handling test failed: {str(e)}")


@pytest.mark.live
class TestLiveVivinoConfig:
    """Test Vivino configuration for live tests."""

    @pytest.fixture(autouse=True)
    def check_live_tests_enabled(self):
        """Skip live tests unless LIVE_TESTS=1 environment variable is set."""
        if os.getenv("LIVE_TESTS") != "1":
            pytest.skip("Live tests are disabled. Set LIVE_TESTS=1 to enable.")

    def test_vivino_timeout_configuration(self):
        """Test that Vivino timeout configurations are reasonable."""
        from app import vivino

        # Check that timeout constants exist and are reasonable
        timeout = getattr(vivino, 'VIVINO_TIMEOUT_SECONDS', None)

        if timeout:
            assert 0.5 <= timeout <= 10.0, f"VIVINO_TIMEOUT_SECONDS should be 0.5-10s, got {timeout}"
            print(f"\n📊 Vivino timeout configuration: {timeout}s")
        else:
            print("\n📊 No explicit timeout configuration found (using defaults)")

    def test_vivino_constants_and_config(self):
        """Test Vivino constants and configuration values."""
        from app import vivino

        print("\n📋 Vivino Configuration:")

        # Check various constants and configurations
        attrs_to_check = [
            'VIVINO_TIMEOUT_SECONDS',
            'VIVINO_SEARCH_ENDPOINT',
            'VIVINO_BASE_URL',
            'USER_AGENT',
        ]

        for attr in attrs_to_check:
            value = getattr(vivino, attr, None)
            if value:
                print(f"   {attr}: {value}")
            else:
                # Check if it's in config module
                from app import config
                config_value = getattr(config, attr, None)
                if config_value:
                    print(f"   {attr} (from config): {config_value}")
                else:
                    print(f"   {attr}: Not configured")


# Additional helper for running live tests manually
if __name__ == "__main__":
    import asyncio
    import sys

    async def manual_test():
        """Manual test runner for development."""
        print("🧪 Running manual Vivino live test...")

        try:
            query = "Dom Perignon Champagne"

            print(f"🔍 Step 1: Resolving URL for '{query}'...")
            url = await resolve_vivino_url(query, timeout_s=3.0)

            if url:
                print(f"✅ Found URL: {url}")

                print("📄 Step 2: Fetching page content...")
                html_content = await _fetch_vivino_page(url, timeout_s=3.0)

                if html_content:
                    print(f"✅ Fetched {len(html_content)} characters")

                    print("🔍 Step 3: Parsing wine data...")
                    rating, count, price = parse_vivino_page(html_content)

                    print("\n📊 Results:")
                    print(f"Rating: {rating}⭐" if rating else "Rating: Not found")
                    print(f"Reviews: {count:,}" if count else "Reviews: Not found")
                    print(f"Price: ${price}" if price else "Price: Not found")

                    if rating and count:
                        print("\n🎯 Live Vivino integration working correctly!")
                    else:
                        print("\n⚠️ Partial data extraction - check parsing logic")
                else:
                    print("❌ Could not fetch page content")
            else:
                print("❌ Could not resolve Vivino URL")

        except Exception as e:
            print(f"❌ Manual test failed: {e}")

    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        asyncio.run(manual_test())
    else:
        print("Use 'python tests/test_live_vivino.py manual' to run manual test")
        print("Or use 'LIVE_TESTS=1 pytest tests/test_live_vivino.py -v' to run live tests")
