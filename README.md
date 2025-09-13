# Wine Deal Scanner

A Python application that watches LastBottle website for new wine deals, enriches them with Vivino ratings and pricing data, and sends notifications via Telegram.

## Features

- 🍷 **Real-time monitoring** of LastBottle website using Playwright
- ⭐ **Vivino enrichment** with ratings, review counts, and average prices
- 📱 **Telegram notifications** with formatted deal information
- 🔄 **Smart deduplication** to avoid repeat notifications
- 🚀 **Async/await** throughout for optimal performance
- ⚡ **Strict timeouts** to ensure responsiveness
- 📝 **Structured logging** with detailed monitoring

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd wine_deal_scanner
```

2. Install dependencies and set up Playwright:
```bash
make setup
```

3. Configure environment variables:
```bash
cp env.example .env
# Edit .env with your actual values
```

## Configuration

Create a `.env` file with the following variables:

```env
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Optional (with defaults)
LASTBOTTLE_URL=https://www.lastbottle.com
VIVINO_TIMEOUT_SECONDS=1.5
DEAL_DEDUP_MINUTES=5
LOG_LEVEL=INFO
```

### Getting Telegram Credentials

1. Create a bot by messaging [@BotFather](https://t.me/botfather) on Telegram
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)

## Usage

```bash
# Run the application
make run

# Format code
make fmt

# Lint code
make lint

# Run tests
make test

# Clean build artifacts
make clean
```

## Architecture

The application consists of several key components:

- **`app/main.py`** - Main application loop with graceful shutdown
- **`app/watcher.py`** - Playwright-based website monitoring
- **`app/extract.py`** - Deal extraction from JSON/DOM
- **`app/vivino.py`** - Vivino API integration with timeouts
- **`app/notify.py`** - Telegram notification formatting and sending
- **`app/models.py`** - Pydantic data models
- **`app/config.py`** - Environment configuration management

## How It Works

1. **Website Monitoring**: Uses Playwright to monitor LastBottle website
   - Listens for XHR/JSON responses containing deal data
   - Falls back to DOM mutation observation
   - Persistent browser session for efficiency

2. **Deal Processing**: 
   - Extracts deal information from API responses or DOM
   - Generates unique keys for deduplication
   - Validates and normalizes data using Pydantic

3. **Vivino Enrichment**:
   - Quick lookup with strict 1.5s timeout
   - Fetches ratings, review counts, and average prices
   - Graceful fallback if data unavailable

4. **Telegram Notifications**:
   - Rich formatting with wine details and pricing
   - Highlights savings and Vivino comparisons
   - Retry logic for reliable delivery

## Development

The project uses modern Python tooling:

- **Python 3.13** with full type hints
- **Pydantic** for data validation
- **Playwright** for browser automation
- **httpx** for async HTTP requests
- **structlog** for structured logging
- **tenacity** for retry logic

## Testing

Run the test suite:

```bash
make test
```

Tests cover:
- Deal key generation and normalization
- JSON extraction with various data formats
- Mock payload processing

## Limitations & TODOs

The application includes TODOs for areas requiring customization:

- **LastBottle selectors**: DOM selectors need updating based on actual website structure
- **API endpoints**: Response monitoring patterns need refinement
- **Vivino API**: May require different API approach or web scraping
- **Rate limiting**: Consider implementing rate limits for external APIs

## License

MIT License - see LICENSE file for details.

