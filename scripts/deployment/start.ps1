# PowerShell version for Windows
# One-command startup script for data collection system

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Data Collection System - Quick Start" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and navigate to deployment directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$deploymentDir = Join-Path $projectRoot "deployment"
Set-Location $deploymentDir

# Step 1: Build image if it doesn't exist
$imageExists = docker images | Select-String "backtester-mvp.*latest"

if (-not $imageExists -or $args[0] -eq "--rebuild") {
    Write-Host "📦 Building Docker image..." -ForegroundColor Yellow
    docker-compose build
    Write-Host ""
} else {
    Write-Host "✓ Docker image exists, skipping build" -ForegroundColor Green
    Write-Host "  (use --rebuild to force rebuild)" -ForegroundColor Gray
    Write-Host ""
}

# Step 2: Check if bulk fetch is needed by comparing expected vs actual cache files
try {
    $allCacheFiles = Get-ChildItem -Path (Join-Path $projectRoot "data\*.csv") -ErrorAction SilentlyContinue
    $cacheCount = ($allCacheFiles | Measure-Object).Count
    
    # Count new format files (simplified naming without date ranges)
    $newFormatCount = ($allCacheFiles | Where-Object { $_.Name -notmatch "_2017-" } | Measure-Object).Count
    
    # Calculate expected count from markets.yaml
    $metadataPath = Join-Path $projectRoot "config\markets.yaml"
    if (Test-Path $metadataPath) {
        $metadata = Get-Content $metadataPath | ConvertFrom-Yaml
        $markets = ($metadata.top_markets | Measure-Object).Count
        $timeframes = ($metadata.timeframes | Measure-Object).Count
        $expectedCount = $markets * $timeframes
    } else {
        $expectedCount = 0
    }
} catch {
    $cacheCount = 0
    $newFormatCount = 0
    $expectedCount = 0
}

# Run bulk fetch if we don't have enough new format files
if ($newFormatCount -lt $expectedCount) {
    Write-Host "📥 Running bulk data collection..." -ForegroundColor Yellow
    Write-Host "   Expected: $expectedCount files (from markets.yaml)" -ForegroundColor Gray
    Write-Host "   Found: $newFormatCount files" -ForegroundColor Gray
    Write-Host "   Fetching all markets/timeframes (existing files will be skipped)" -ForegroundColor Gray
    Write-Host "   Estimated time: 2-5 hours depending on number of markets" -ForegroundColor Gray
    Write-Host ""
    docker-compose run --rm bulk-fetch
    Write-Host ""
    
    # Verify bulk fetch completed
    try {
        $finalCount = (Get-ChildItem -Path (Join-Path $projectRoot "data\*.csv") -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "_2017-" } | Measure-Object).Count
        if ($finalCount -eq 0) {
            Write-Host "⚠️  Warning: Bulk fetch completed but no cache files found" -ForegroundColor Yellow
            Write-Host "   Check logs: docker-compose logs bulk-fetch" -ForegroundColor Gray
        } else {
            Write-Host "✓ Bulk fetch completed - found $finalCount cache files" -ForegroundColor Green
        }
    } catch {
        Write-Host "⚠️  Could not verify cache files after bulk fetch" -ForegroundColor Yellow
    }
    Write-Host ""
} else {
    Write-Host "✓ Found $newFormatCount/$expectedCount cache files" -ForegroundColor Green
    Write-Host "  Bulk fetch skipped - all expected data exists" -ForegroundColor Gray
    Write-Host ""
}

# Step 3: Start scheduler (skip if update lock exists)
$lockFile = Join-Path $projectRoot "artifacts\locks\update.lock"
if (Test-Path $lockFile) {
    Write-Host "⏸  Update in progress (lock present) - skipping scheduler restart" -ForegroundColor Yellow
} else {
    Write-Host "🚀 Starting scheduler daemon..." -ForegroundColor Yellow
    docker-compose up -d scheduler
}

# Step 4: Show status
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✓ System is running!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Scheduler status: $(docker-compose ps scheduler --format '{{.Status}}')" -ForegroundColor Gray
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  View logs:     docker-compose logs -f scheduler" -ForegroundColor White
Write-Host "  Stop:          docker-compose stop scheduler" -ForegroundColor White
Write-Host "  Update data:   docker-compose run --rm bulk-fetch" -ForegroundColor White
Write-Host "  Run backtest:  python main.py (run separately - not in Docker)" -ForegroundColor White
Write-Host ""
Write-Host "Note: Backtest runs directly on host for development" -ForegroundColor Yellow
Write-Host "      It will use data from ./data/ (shared with Docker)" -ForegroundColor Yellow
Write-Host ""

