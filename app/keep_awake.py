#!/usr/bin/env python3
"""
Keep computer awake while the wine deal scanner is running.
Prevents automatic sleep/idle during deal monitoring.
"""

import asyncio
import platform
import subprocess
import sys
from typing import Optional

class KeepAwake:
    """Prevents computer from sleeping while monitoring deals."""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.caffeinate_process: Optional[subprocess.Popen] = None
        
    async def start(self):
        """Start keeping the computer awake."""
        if self.system == "darwin":  # macOS
            await self._start_caffeinate()
        elif self.system == "windows":
            await self._start_windows_power()
        elif self.system == "linux":
            await self._start_linux_power()
        else:
            print(f"⚠️  Sleep prevention not supported on {self.system}")
            
    async def stop(self):
        """Stop keeping the computer awake."""
        if self.caffeinate_process:
            try:
                self.caffeinate_process.terminate()
                await asyncio.sleep(0.5)
                if self.caffeinate_process.poll() is None:
                    self.caffeinate_process.kill()
                self.caffeinate_process = None
                print("✅ Sleep prevention stopped")
            except Exception as e:
                print(f"⚠️  Error stopping sleep prevention: {e}")
    
    async def _start_caffeinate(self):
        """Start caffeinate on macOS to prevent sleep."""
        try:
            # caffeinate -d -u -t 86400 (prevent display sleep, prevent user idle, for 24 hours)
            self.caffeinate_process = subprocess.Popen([
                "caffeinate", "-d", "-u", "-t", "86400"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("☕ Sleep prevention started (macOS caffeinate)")
        except Exception as e:
            print(f"⚠️  Failed to start caffeinate: {e}")
            
    async def _start_windows_power(self):
        """Start power management prevention on Windows."""
        try:
            # Use powercfg to prevent sleep
            subprocess.run([
                "powercfg", "/change", "monitor-timeout-ac", "0"
            ], check=True, capture_output=True)
            subprocess.run([
                "powercfg", "/change", "standby-timeout-ac", "0"
            ], check=True, capture_output=True)
            print("💻 Sleep prevention started (Windows powercfg)")
        except Exception as e:
            print(f"⚠️  Failed to start Windows sleep prevention: {e}")
            
    async def _start_linux_power(self):
        """Start power management prevention on Linux."""
        try:
            # Use systemctl to prevent sleep
            subprocess.run([
                "systemctl", "mask", "sleep.target", "suspend.target", 
                "hibernate.target", "hybrid-sleep.target"
            ], check=True, capture_output=True)
            print("🐧 Sleep prevention started (Linux systemctl)")
        except Exception as e:
            print(f"⚠️  Failed to start Linux sleep prevention: {e}")

# Global instance for easy access
keep_awake = KeepAwake()

async def start_keep_awake():
    """Start keeping the computer awake."""
    await keep_awake.start()

async def stop_keep_awake():
    """Stop keeping the computer awake."""
    await keep_awake.stop()
