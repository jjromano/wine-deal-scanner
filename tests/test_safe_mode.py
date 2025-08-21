"""Tests for safe mode functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.watcher import DealWatcher
from app import config


class TestSafeModeFeatures:
    """Tests for safe mode and request blocking functionality."""
    
    @pytest.mark.asyncio
    async def test_user_agent_configuration(self) -> None:
        """Test that custom user agent is used."""
        watcher = DealWatcher()
        
        with patch('app.watcher.async_playwright') as mock_playwright:
            mock_playwright_instance = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            
            await watcher._setup_browser()
            
            # Verify user agent was passed to context
            mock_browser.new_context.assert_called_once()
            call_args = mock_browser.new_context.call_args[1]
            assert call_args['user_agent'] == config.USER_AGENT
    
    @pytest.mark.asyncio
    async def test_safe_mode_request_blocking_setup(self) -> None:
        """Test that request blocking is set up in safe mode."""
        watcher = DealWatcher()
        
        with patch.object(config, 'SAFE_MODE', True), \
             patch.object(watcher, '_setup_request_blocking') as mock_setup_blocking:
            
            # Mock browser setup
            with patch('app.watcher.async_playwright') as mock_playwright:
                mock_playwright_instance = AsyncMock()
                mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
                
                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                
                mock_playwright_instance.chromium.launch.return_value = mock_browser
                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                
                watcher.page = mock_page  # Set page for blocking setup
                
                await watcher._setup_browser()
                
                # Verify request blocking was set up
                mock_setup_blocking.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_mode_disabled_no_blocking(self) -> None:
        """Test that request blocking is not set up when safe mode is disabled."""
        watcher = DealWatcher()
        
        with patch.object(config, 'SAFE_MODE', False), \
             patch.object(watcher, '_setup_request_blocking') as mock_setup_blocking:
            
            # Mock browser setup
            with patch('app.watcher.async_playwright') as mock_playwright:
                mock_playwright_instance = AsyncMock()
                mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
                
                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                
                mock_playwright_instance.chromium.launch.return_value = mock_browser
                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                
                await watcher._setup_browser()
                
                # Verify request blocking was NOT set up
                mock_setup_blocking.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_request_blocking_logic(self) -> None:
        """Test the request blocking logic."""
        watcher = DealWatcher()
        mock_page = AsyncMock()
        watcher.page = mock_page
        
        # Track route handler
        route_handler = None
        
        async def capture_route_handler(pattern, handler):
            nonlocal route_handler
            route_handler = handler
        
        mock_page.route.side_effect = capture_route_handler
        
        await watcher._setup_request_blocking()
        
        # Verify route was set up
        mock_page.route.assert_called_once_with("**/*", route_handler)
        assert route_handler is not None
        
        # Test blocking different resource types
        test_cases = [
            # (resource_type, url, should_block)
            ("image", "https://example.com/image.jpg", True),
            ("media", "https://example.com/video.mp4", True),
            ("font", "https://example.com/font.woff", True),
            ("xhr", "https://example.com/api/data", False),
            ("fetch", "https://example.com/api/fetch", False),
            ("document", "https://example.com/page.html", False),
            ("stylesheet", "https://example.com/style.css", False),
            ("script", "https://example.com/script.js", False),
            ("other", "https://example.com/unknown", True),  # Block by default
        ]
        
        for resource_type, url, should_block in test_cases:
            mock_route = AsyncMock()
            mock_request = MagicMock()
            mock_request.url = url
            mock_request.resource_type = resource_type
            mock_route.request = mock_request
            
            watcher.blocked_requests_count = 0  # Reset counter
            
            await route_handler(mock_route)
            
            if should_block:
                mock_route.abort.assert_called_once()
                assert watcher.blocked_requests_count == 1
            else:
                mock_route.continue_.assert_called_once()
                assert watcher.blocked_requests_count == 0
            
            # Reset mocks for next iteration
            mock_route.reset_mock()
    
    @pytest.mark.asyncio
    async def test_analytics_domain_blocking(self) -> None:
        """Test that analytics domains are blocked."""
        watcher = DealWatcher()
        mock_page = AsyncMock()
        watcher.page = mock_page
        
        # Capture route handler
        route_handler = None
        
        async def capture_route_handler(pattern, handler):
            nonlocal route_handler
            route_handler = handler
        
        mock_page.route.side_effect = capture_route_handler
        
        await watcher._setup_request_blocking()
        
        # Test analytics domains
        analytics_urls = [
            "https://www.google-analytics.com/analytics.js",
            "https://www.googletagmanager.com/gtm.js",
            "https://connect.facebook.net/en_US/fbevents.js",
            "https://doubleclick.net/ads",
            "https://googlesyndication.com/ads",
        ]
        
        for url in analytics_urls:
            mock_route = AsyncMock()
            mock_request = MagicMock()
            mock_request.url = url
            mock_request.resource_type = "script"  # Should normally be allowed
            mock_route.request = mock_request
            
            watcher.blocked_requests_count = 0  # Reset counter
            
            await route_handler(mock_route)
            
            # Should be blocked despite being a script
            mock_route.abort.assert_called_once()
            assert watcher.blocked_requests_count == 1
            
            mock_route.reset_mock()
    
    def test_debounce_timing(self) -> None:
        """Test debounce timing configuration."""
        watcher = DealWatcher()
        
        # Test debounce delay is in expected range (300-500ms)
        assert 0.3 <= watcher.debounce_delay <= 0.5
        assert watcher.debounce_delay == 0.4  # Default value
    
    @pytest.mark.asyncio
    async def test_dom_debouncing(self) -> None:
        """Test DOM check debouncing functionality."""
        watcher = DealWatcher()
        mock_page = AsyncMock()
        watcher.page = mock_page
        
        # Mock page evaluation to return check requested
        mock_page.evaluate.return_value = True
        
        # First call should proceed
        await watcher._check_dom_for_deals(AsyncMock())
        
        # Verify page was evaluated and content was fetched
        assert mock_page.evaluate.call_count >= 1
        assert mock_page.content.call_count >= 1
        
        # Reset mocks
        mock_page.reset_mock()
        mock_page.evaluate.return_value = True
        
        # Second call immediately after should be debounced (skipped)
        await watcher._check_dom_for_deals(AsyncMock())
        
        # Should not have proceeded due to debouncing
        mock_page.evaluate.assert_called_once()  # Only the check for dealCheckRequested
        mock_page.content.assert_not_called()  # Should not fetch content
    
    @pytest.mark.asyncio
    async def test_heartbeat_logging(self) -> None:
        """Test heartbeat logging functionality."""
        watcher = DealWatcher()
        watcher.page = AsyncMock()
        watcher.running = True
        watcher.blocked_requests_count = 42
        watcher.last_deal_key = "test_wine_2020_50.0"
        
        with patch('app.watcher.logger') as mock_logger, \
             patch('time.time') as mock_time:
            
            # Set up time to trigger heartbeat (more than 60s since last)
            mock_time.return_value = 1000.0
            watcher.last_heartbeat = 900.0  # 100 seconds ago
            
            # First call should log heartbeat
            await watcher._log_heartbeat()
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[1]
            
            # Verify heartbeat log contains expected fields
            assert call_args["mode"] == "event"
            assert call_args["page_ready"] is True
            assert call_args["blocked_requests_count"] == 42
            assert call_args["last_deal_key"] == "test_wine_2020_50.0"
            assert call_args["safe_mode"] == config.SAFE_MODE
            assert "seen_deals_count" in call_args
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Second call immediately after should not log (60s interval)
            await watcher._log_heartbeat()
            
            mock_logger.info.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_heartbeat_timing(self) -> None:
        """Test heartbeat timing interval."""
        watcher = DealWatcher()
        watcher.page = AsyncMock()
        watcher.running = True
        
        import time
        
        with patch('app.watcher.logger') as mock_logger, \
             patch('time.time') as mock_time:
            
            # Set initial time
            mock_time.return_value = 1000.0
            watcher.last_heartbeat = 1000.0
            
            # Call within 60s window - should not log
            mock_time.return_value = 1030.0  # 30 seconds later
            await watcher._log_heartbeat()
            mock_logger.info.assert_not_called()
            
            # Call after 60s window - should log
            mock_time.return_value = 1070.0  # 70 seconds from start
            await watcher._log_heartbeat()
            mock_logger.info.assert_called_once()


class TestSafeModeIntegration:
    """Integration tests for safe mode features."""
    
    @pytest.mark.asyncio
    async def test_safe_mode_configuration_loading(self) -> None:
        """Test that safe mode configuration is loaded correctly."""
        # Test default values
        assert hasattr(config, 'SAFE_MODE')
        assert hasattr(config, 'USER_AGENT')
        
        # Test that values are of correct type
        assert isinstance(config.SAFE_MODE, bool)
        assert isinstance(config.USER_AGENT, str)
        
        # Test default user agent format
        assert "LastBottleWatcher" in config.USER_AGENT
        assert "@" in config.USER_AGENT  # Should contain email placeholder
    
    def test_watcher_initialization_with_safe_mode(self) -> None:
        """Test watcher initialization includes safe mode tracking."""
        watcher = DealWatcher()
        
        # Verify safe mode tracking attributes are initialized
        assert hasattr(watcher, 'blocked_requests_count')
        assert hasattr(watcher, 'last_deal_key')
        assert hasattr(watcher, 'last_heartbeat')
        assert hasattr(watcher, 'last_dom_check_time')
        assert hasattr(watcher, 'debounce_delay')
        
        # Verify initial values
        assert watcher.blocked_requests_count == 0
        assert watcher.last_deal_key is None
        assert watcher.debounce_delay == 0.4
        assert watcher.last_dom_check_time == 0.0
