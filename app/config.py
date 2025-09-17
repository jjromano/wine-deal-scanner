import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def _env_bool(name: str, default: bool=False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1","true","t","yes","y","on")

DEBUG     = _env_bool("DEBUG", False)
SAFE_MODE = _env_bool("SAFE_MODE", False)
HEADFUL   = _env_bool("HEADFUL", False)

# FORCE a normal desktop UA (ignore env until stable)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

if DEBUG:
    print(f"[config] UA set to: {USER_AGENT[:60]}...")

LASTBOTTLE_URL = os.getenv("LASTBOTTLE_URL", "https://www.lastbottlewines.com/")

GENERIC_MARKERS = (
    "last bottle - your daily purveyor of fine wine",
    "last bottle – your daily purveyor of fine wine",
)

def is_generic_title(title: str) -> bool:
    t = (title or "").strip().lower()
    return (not t) or any(m in t for m in GENERIC_MARKERS)

def is_price_valid(x) -> bool:
    try:
        return x is not None and float(x) >= 5.0
    except:
        return False