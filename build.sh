#!/bin/bash
# Build script for Railway deployment

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

echo "✅ Build complete!"
