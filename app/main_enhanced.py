#!/usr/bin/env python3
"""
Wine Deal Scanner - Monitor LastBottle for new deals and send Telegram notifications.

Features:
- Monitor LastBottle for new deals
- Enhanced Vivino lookups with advanced anti-detection
- Send Telegram notifications with Vivino data
- Fallback to simple notifications if Vivino fails

Usage:
    python -m app.main_enhanced
"""

import asyncio
import sys
from app.watcher_enhanced import run_enhanced_watcher

async def main():
    print("🍷 Wine Deal Scanner")
    print("=" * 40)
    
    try:
        await run_enhanced_watcher()
    except KeyboardInterrupt:
        print("\n⏹️  Scanner stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
