#!/bin/bash
# One-command startup script for data collection system

set -e

echo "=========================================="
echo "Data Collection System - Quick Start"
echo "=========================================="
echo ""

# Step 1: Build image if it doesn't exist or is outdated
if ! docker images | grep -q "backtester-mvp.*latest" || [ "$1" == "--rebuild" ]; then
    echo "📦 Building Docker image..."
    docker-compose build
    echo ""
else
    echo "✓ Docker image exists, skipping build"
    echo "  (use --rebuild to force rebuild)"
    echo ""
fi

# Step 2: Check if bulk fetch is needed by comparing expected vs actual cache files
# Count new format files (simplified naming without date ranges)
NEW_FORMAT_COUNT=$(ls -1 data/cache/*.csv 2>/dev/null | grep -v "_2017-" | wc -l | tr -d ' ' || echo "0")

# Calculate expected count from exchange_metadata.yaml
EXPECTED_COUNT=$(python3 -c "
import yaml
from pathlib import Path
try:
    metadata = yaml.safe_load(open('config/exchange_metadata.yaml'))
    markets = len(metadata.get('top_markets', []))
    timeframes = len(metadata.get('timeframes', []))
    print(markets * timeframes)
except:
    print('0')
" 2>/dev/null || echo "0")

# Run bulk fetch if we don't have enough new format files
if [ "$NEW_FORMAT_COUNT" -lt "$EXPECTED_COUNT" ]; then
    echo "📥 Running bulk data collection..."
    echo "   Expected: $EXPECTED_COUNT files (from exchange_metadata.yaml)"
    echo "   Found: $NEW_FORMAT_COUNT files"
    echo "   Fetching all markets/timeframes (existing files will be skipped)"
    echo "   Estimated time: 2-5 hours depending on number of markets"
    echo ""
    docker-compose run --rm bulk-fetch
    echo ""
    
    # Verify bulk fetch completed
    FINAL_COUNT=$(ls -1 data/cache/*.csv 2>/dev/null | grep -v "_2017-" | wc -l | tr -d ' ' || echo "0")
    if [ "$FINAL_COUNT" == "0" ]; then
        echo "⚠️  Warning: Bulk fetch completed but no cache files found"
        echo "   Check logs: docker-compose logs bulk-fetch"
    else
        echo "✓ Bulk fetch completed - found $FINAL_COUNT cache files"
    fi
    echo ""
else
    echo "✓ Found $NEW_FORMAT_COUNT/$EXPECTED_COUNT cache files"
    echo "  Bulk fetch skipped - all expected data exists"
    echo ""
fi

# Step 3: Start scheduler
echo "🚀 Starting scheduler daemon..."
docker-compose up -d scheduler

# Step 4: Show status
echo ""
echo "=========================================="
echo "✓ System is running!"
echo "=========================================="
echo ""
echo "Scheduler: $(docker-compose ps scheduler --format '{{.Status}}')"
echo ""
echo "Useful commands:"
echo "  View logs:     docker-compose logs -f scheduler"
echo "  Stop:          docker-compose stop scheduler"
echo "  Update data:   docker-compose run --rm bulk-fetch"
echo "  Run backtest:  python main.py (run separately - not in Docker)"
echo ""
echo "Note: Backtest runs directly on host for development"
echo "      It will use data from ./data/cache/ (shared with Docker)"
echo ""

