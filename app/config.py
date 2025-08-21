"""Configuration management for the wine deal scanner."""

import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_env_var(key: str, default: str | None = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value


# Required configuration
LASTBOTTLE_URL: str = get_env_var("LASTBOTTLE_URL", "https://www.lastbottle.com")
TELEGRAM_BOT_TOKEN: str = get_env_var("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str = get_env_var("TELEGRAM_CHAT_ID")

# Optional configuration with defaults
VIVINO_TIMEOUT_SECONDS: float = float(get_env_var("VIVINO_TIMEOUT_SECONDS", "1.5"))
DEAL_DEDUP_MINUTES: int = int(get_env_var("DEAL_DEDUP_MINUTES", "5"))
LOG_LEVEL: str = get_env_var("LOG_LEVEL", "INFO")

# Safe mode and user agent configuration
SAFE_MODE: bool = get_env_var("SAFE_MODE", "true").lower() == "true"
USER_AGENT: str = get_env_var("USER_AGENT", "LastBottleWatcher/0.1 (+you@example.com)")
