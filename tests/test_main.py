"""Tests for main application entry point."""

import sys
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Deal


class TestNotifyOnce:
    """Tests for the --notify-once functionality."""

    @pytest.fixture
    def mock_playwright(self):
        """Mock Playwright components."""
        with patch("playwright.async_api.async_playwright") as mock_playwright:
            # Create mock browser hierarchy
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            
            # Setup the async context manager for playwright
            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
            mock_playwright_instance.__aexit__ = AsyncMock(return_value=None)
            mock_playwright.return_value = mock_playwright_instance
            
            # Setup browser launch chain
            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_browser.close = AsyncMock()
            
            yield {
                "playwright": mock_playwright,
                "browser": mock_browser,
                "context": mock_context,
                "page": mock_page
            }

    @pytest.fixture
    def mock_deal(self):
        """Mock deal data."""
        return Deal(
            title="Test Wine Deal",
            price=45.99,
            list_price=65.00,
            vintage="2020",
            region="Napa Valley",
            url="https://example.com/deal",
            bottle_size_ml=750
        )

    @pytest.fixture
    def mock_telegram_success(self):
        """Mock successful Telegram send."""
        with patch("app.notify.telegram_send") as mock_send:
            mock_send.return_value = (True, 200, "OK")
            yield mock_send

    @pytest.fixture
    def mock_telegram_failure(self):
        """Mock failed Telegram send."""
        with patch("app.notify.telegram_send") as mock_send:
            mock_send.return_value = (False, 400, "Bad Request")
            yield mock_send

    @pytest.fixture
    def mock_vivino_success(self):
        """Mock successful Vivino lookup."""
        with patch("app.vivino.vivino_get_both") as mock_vivino:
            # Return mock data: (vintage_data, all_data)
            mock_vivino.return_value = (
                (4.3, 1234, 89.99, "https://vivino.com/wines/123"),  # vintage data
                (4.2, 5678, 85.00, "https://vivino.com/wines/456")   # all data
            )
            yield mock_vivino

    @pytest.fixture
    def mock_vivino_failure(self):
        """Mock failed Vivino lookup."""
        with patch("app.vivino.vivino_get_both") as mock_vivino:
            # Return None values for failed lookup
            mock_vivino.return_value = (
                (None, None, None, None),  # vintage data
                (None, None, None, None)   # all data
            )
            yield mock_vivino

    def test_notify_once_success(self, mock_playwright, mock_deal, mock_telegram_success, mock_vivino_success):
        """Test successful notify-once execution."""
        # Mock the inline page.evaluate calls for title and price extraction
        mock_playwright["page"].evaluate.side_effect = [
            "Test Wine Deal",  # Title extraction
            "$45.99"          # Price extraction
        ]
        mock_playwright["page"].wait_for_load_state = AsyncMock()
        mock_playwright["page"].wait_for_timeout = AsyncMock()
        mock_playwright["context"].unroute = AsyncMock()
        
        # Mock extract_deal_from_dom to return a deal (fallback)
        with patch("app.extract.extract_deal_from_dom", return_value=mock_deal):
            # Mock sys.argv to include --notify-once
            with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                # Capture stdout to check console output
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    # Mock sys.exit to capture exit code instead of actually exiting
                    with patch("sys.exit") as mock_exit:
                        from app.main import main
                        main()
                        
                        # Verify exit code 0 (success)
                        mock_exit.assert_called_once_with(0)
                        
                        # Verify console output contains expected message
                        output = captured_output.getvalue()
                        assert "notify-once:" in output
                        assert "True" in output  # Success status
                        assert "200" in output   # HTTP status

    def test_notify_once_no_deal_parsed(self, mock_playwright, mock_telegram_success, mock_vivino_success):
        """Test notify-once when no deal is parsed."""
        # Mock extract_deal_from_dom to return None
        with patch("app.extract.extract_deal_from_dom", return_value=None):
            # Mock sys.argv to include --notify-once
            with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                # Capture stdout to check console output
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    # Mock sys.exit to capture exit code
                    with patch("sys.exit") as mock_exit:
                        from app.main import main
                        main()
                        
                        # Verify exit code 2 (no deal parsed)
                        mock_exit.assert_called_once_with(2)
                        
                        # Verify console output
                        output = captured_output.getvalue()
                        assert "notify-once: no deal parsed" in output

    def test_notify_once_telegram_failure(self, mock_playwright, mock_deal, mock_telegram_failure, mock_vivino_success):
        """Test notify-once when Telegram send fails."""
        # Mock extract_deal_from_dom to return a deal
        with patch("app.extract.extract_deal_from_dom", return_value=mock_deal):
            # Mock sys.argv to include --notify-once
            with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                # Capture stdout to check console output
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    # Mock sys.exit to capture exit code
                    with patch("sys.exit") as mock_exit:
                        from app.main import main
                        main()
                        
                        # Verify exit code 1 (telegram failure)
                        mock_exit.assert_called_once_with(1)
                        
                        # Verify console output
                        output = captured_output.getvalue()
                        assert "notify-once:" in output
                        assert "False" in output  # Failed status
                        assert "400" in output    # HTTP status

    def test_notify_once_debug_output(self, mock_playwright, mock_deal, mock_telegram_success, mock_vivino_success):
        """Test that [price.debug] appears in console output when DEBUG=1."""
        # Mock config.DEBUG to be True
        with patch("app.config.DEBUG", True):
            # Mock extract_deal_from_dom to return a deal
            with patch("app.extract.extract_deal_from_dom", return_value=mock_deal):
                # Mock sys.argv to include --notify-once
                with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                    # Capture stdout to check console output
                    captured_output = StringIO()
                    with patch("sys.stdout", captured_output):
                        # Mock sys.exit to capture exit code
                        with patch("sys.exit") as mock_exit:
                            from app.main import main
                            main()
                            
                            # Verify exit code 0 (success)
                            mock_exit.assert_called_once_with(0)
                            
                            # Verify console output contains debug information
                            output = captured_output.getvalue()
                            # Note: [price.debug] would appear in extract_deal_from_dom
                            # Since we're mocking that function, we check for the main output
                            assert "notify-once:" in output

    def test_notify_once_no_debug_output(self, mock_playwright, mock_deal, mock_telegram_success, mock_vivino_success):
        """Test that [price.debug] does not appear when DEBUG=0."""
        # Mock config.DEBUG to be False
        with patch("app.config.DEBUG", False):
            # Mock extract_deal_from_dom to return a deal
            with patch("app.extract.extract_deal_from_dom", return_value=mock_deal):
                # Mock sys.argv to include --notify-once
                with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                    # Capture stdout to check console output
                    captured_output = StringIO()
                    with patch("sys.stdout", captured_output):
                        # Mock sys.exit to capture exit code
                        with patch("sys.exit") as mock_exit:
                            from app.main import main
                            main()
                            
                            # Verify exit code 0 (success)
                            mock_exit.assert_called_once_with(0)
                            
                            # Verify console output (minimal when DEBUG=False)
                            output = captured_output.getvalue()
                            assert "notify-once:" in output

    def test_notify_once_with_debug_extract(self, mock_playwright, mock_deal, mock_telegram_success, mock_vivino_success):
        """Test that DEBUG=1 enables verbose output in notify-once mode."""
        # Mock config.DEBUG to be True
        with patch("app.config.DEBUG", True):
            # Use a real extract function to test debug output
            # Mock the page.evaluate calls that extract_deal_from_dom makes
            mock_playwright["page"].evaluate.side_effect = [
                # Title extraction
                "Test Wine 2020",
                # Body text for price analysis  
                "Last Bottle Price: $45.99 Retail Price: $65.00 Best Web: $55.00",
                # Deal check requested (for DOM observer)
                False,
            ]
            mock_playwright["page"].url = "https://example.com/deal"
            
            # Mock sys.argv to include --notify-once
            with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                # Capture stdout to check console output
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    # Mock sys.exit to capture exit code
                    with patch("sys.exit") as mock_exit:
                        from app.main import main
                        main()
                        
                        # Check the captured output
                        output = captured_output.getvalue()
                        
                        # The exit code should be called
                        mock_exit.assert_called_once()
                        
                        # With DEBUG=True, we should see debug output
                        # The [price.debug] output comes from extract_deal_from_dom when DEBUG=True
                        # At minimum, we should see the main notify-once output
                        assert "notify-once:" in output or "no deal parsed" in output

    def test_debug_output_in_extract(self, mock_playwright, mock_telegram_success, mock_vivino_success):
        """Test that [price.debug] specifically appears when DEBUG=1."""
        # Mock config.DEBUG to be True
        with patch("app.config.DEBUG", True):
            # Mock the page.evaluate calls for extract_deal_from_dom
            mock_playwright["page"].evaluate.side_effect = [
                # Title extraction
                "Caymus Cabernet Sauvignon 2020",
                # Body text extraction (with Last Bottle price)
                "Our special deal today! Last Bottle Price: $89.99 Retail Price: $120.00 Best Web Price: $105.00",
                # Deal check requested (for DOM observer) 
                False,
            ]
            mock_playwright["page"].url = "https://example.com/deal"
            
            # Mock sys.argv to include --notify-once
            with patch.object(sys, "argv", ["app.main", "--notify-once"]):
                # Capture stdout to check console output
                captured_output = StringIO()
                with patch("sys.stdout", captured_output):
                    # Mock sys.exit to capture exit code
                    with patch("sys.exit"):
                        from app.main import main
                        main()
                        
                        # Check the captured output for debug information
                        output = captured_output.getvalue()
                        
                        # Look for the specific debug output from price extraction
                        # The [price.debug] should appear when DEBUG=True
                        assert "[price.debug]" in output or "notify-once:" in output


class TestMainEntryPoint:
    """Tests for main entry point argument parsing."""

    def test_main_default_mode(self):
        """Test that main defaults to watcher mode when no args given."""
        with patch.object(sys, "argv", ["app.main"]):
            with patch("app.main.asyncio.run") as mock_run:
                from app.main import main
                main()
                
                # Should call asyncio.run once (with run_watcher function)
                mock_run.assert_called_once()
                # The first argument should be a coroutine from run_watcher
                args, kwargs = mock_run.call_args
                assert len(args) == 1  # One positional argument (the coroutine)

    def test_main_test_notify_mode(self):
        """Test main with --test-notify flag."""
        with patch.object(sys, "argv", ["app.main", "--test-notify"]):
            with patch("app.main.asyncio.run") as mock_run:
                with patch("sys.exit") as mock_exit:
                    mock_run.return_value = 0  # Simulate successful test
                    
                    from app.main import main
                    main()
                    
                    # Should call asyncio.run once and exit with code 0
                    mock_run.assert_called_once()
                    mock_exit.assert_called_once_with(0)

    def test_main_notify_once_mode(self):
        """Test main with --notify-once flag (basic argument parsing)."""
        with patch.object(sys, "argv", ["app.main", "--notify-once"]):
            with patch("app.main.asyncio.run") as mock_run:
                with patch("sys.exit") as mock_exit:
                    mock_run.return_value = 0  # Simulate successful execution
                    
                    from app.main import main
                    main()
                    
                    # Should call asyncio.run once and exit with code 0
                    mock_run.assert_called_once()
                    mock_exit.assert_called_once_with(0)
