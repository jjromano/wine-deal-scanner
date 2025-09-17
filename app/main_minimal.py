#!/usr/bin/env python3
"""
Minimal wine deal scanner - focuses only on core functionality:
1. Monitor LastBottle for new deals
2. Send Telegram notifications when deals change
"""

import asyncio
import sys
from app.watcher_minimal import run_minimal_watcher

async def main():
    print("🍷 Minimal Wine Deal Scanner")
    print("=" * 40)
    
    try:
        await run_minimal_watcher()
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
