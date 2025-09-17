# Wine Deal Scanner

A Python application that monitors LastBottle website for new wine deals, enriches them with Vivino ratings and pricing data, and sends notifications via Telegram.

## Features

- 🍷 **Real-time monitoring** of LastBottle website using Playwright
- ⭐ **Vivino enrichment** with ratings, review counts, and average prices
- 📱 **Telegram notifications** with formatted deal information
- 🔄 **Smart deal detection** to avoid repeat notifications
- 🚀 **Async/await** throughout for optimal performance
- 🛡️ **Advanced anti-detection** for Vivino lookups
- 📝 **Fallback notifications** if Vivino fails

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
DEBUG=false
HEADFUL=false
LASTBOTTLE_URL=https://www.lastbottlewines.com/
```

### Getting Telegram Credentials

1. Create a bot by messaging [@BotFather](https://t.me/botfather) on Telegram
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)

## Usage

```bash
# Run the application
python -m app.main

# Run with debug output
DEBUG=1 python -m app.main

# Run with visible browser (for debugging)
HEADFUL=1 python -m app.main
```

## Architecture

The application consists of several key components:

- **`app/main.py`** - Main application entry point
- **`app/watcher.py`** - Playwright-based website monitoring with Vivino enrichment
- **`app/domutils.py`** - Deal extraction from LastBottle DOM
- **`app/vivino.py`** - Vivino lookup with anti-detection
- **`app/notify.py`** - Telegram notification formatting and sending
- **`app/models.py`** - Pydantic data models
- **`app/config.py`** - Environment configuration management

## How It Works

1. **Website Monitoring**: Uses Playwright to monitor LastBottle website
   - Refreshes page periodically to detect new deals
   - Extracts wine title and "Last Bottle" price from DOM
   - Generates unique deal IDs for deduplication

2. **Deal Processing**: 
   - Extracts deal information using robust CSS selectors
   - Validates and normalizes data using Pydantic
   - Skips generic titles and invalid prices

3. **Vivino Enrichment**:
   - Enhanced anti-detection with stealth browser contexts
   - Searches for both vintage-specific and overall wine data
   - Handles non-vintage wines appropriately
   - Graceful fallback if blocked or data unavailable

4. **Telegram Notifications**:
   - Rich formatting with wine details and Vivino data
   - Direct links to Vivino wine pages when available
   - Fallback to search links if direct links unavailable
   - Always includes LastBottle link

## Development

The project uses modern Python tooling:

- **Python 3.13** with full type hints
- **Pydantic** for data validation
- **Playwright** for browser automation
- **httpx** for async HTTP requests

## Testing

Run the test suite:

```bash
make test
```

Tests cover:
- Vivino data parsing and extraction
- Telegram notification formatting
- Data model validation

## License

MIT License - see LICENSE file for details.