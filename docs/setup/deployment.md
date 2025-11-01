# Deployment Guide

## Docker Deployment (Recommended)

### Prerequisites

- Docker and Docker Compose installed
- At least 10GB free disk space for data cache
- Internet connection for data fetching

### Initial Setup

1. **Build the Docker image:**
```bash
docker-compose build
```

2. **Initial data collection:**
```bash
docker-compose run --rm bulk-fetch
```

This will fetch all historical data for all markets/timeframes defined in `exchange_metadata.yaml`. This may take several hours depending on the number of markets.

3. **Start the scheduler service:**
```bash
docker-compose up -d scheduler
```

The scheduler will run continuously and update data daily at 1:00 AM UTC (configurable).

### Running Backtests

Run backtests directly on your host (development workflow):

```bash
python main.py
```

### Configuration

#### Update Schedule

Set environment variables in `docker-compose.yml` or export before running:

```bash
export UPDATE_HOUR=1      # Hour (0-23) UTC
export UPDATE_MINUTE=0    # Minute (0-59)
export TZ=America/New_York  # Timezone for logs

docker-compose up -d scheduler
```

Or modify `docker-compose.yml` directly:

```yaml
services:
  scheduler:
    environment:
      - UPDATE_HOUR=1
      - UPDATE_MINUTE=0
      - TZ=America/New_York
```

#### Data Collection Start Date

Edit `config/data.yaml`:

```yaml
data:
  historical_start_date: "2017-01-01"  # Change as needed
```

### Service Management

```bash
# View scheduler logs
docker-compose logs -f scheduler

# Stop scheduler
docker-compose stop scheduler

# Restart scheduler
docker-compose restart scheduler

# View all running containers
docker-compose ps
```

### Volume Management

All data is persisted in host directories:

- `./data` - Cached OHLCV data (CSV files)
- `./config` - Configuration files
- `./artifacts/logs` - Application logs
- `./artifacts/reports` - Backtest reports
- `./artifacts/performance` - Performance metrics

These directories are mounted as volumes, so data persists across container restarts.

### Updating the Application

1. **Pull latest code:**
```bash
git pull
```

2. **Rebuild image:**
```bash
docker-compose build
```

3. **Restart services:**
```bash
docker-compose up -d scheduler
```

Existing data cache will be preserved.

#### Graceful Scheduler Restarts and Update Lock

- The scheduler is configured with a long stop grace period so in-flight updates can finish on deploy:

```yaml
services:
  scheduler:
    stop_signal: SIGTERM
    stop_grace_period: 2h
```

- An update lock at `artifacts/locks/update.lock` prevents restarts while an update is running. The startup scripts skip restarting the scheduler if the lock exists.

```bash
# scripts/deployment/start.sh (excerpt)
LOCK_FILE="$PROJECT_ROOT/artifacts/locks/update.lock"
if [ -f "$LOCK_FILE" ]; then
  echo "Update in progress; skipping scheduler restart."
else
  docker-compose up -d scheduler
fi
```

## Manual Deployment (Non-Docker)

### Prerequisites

- Python 3.11+
- pip package manager
- System scheduler (cron on Linux/Mac, Task Scheduler on Windows)

### Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Initial data collection:**
```bash
python scripts/data/bulk_fetch.py
```

3. **Setup daily updates:**

**Linux/Mac (cron):**
```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 1 AM UTC)
0 1 * * * cd /path/to/atlas && python -m backtester.services.update_runner >> artifacts/logs/cron.log 2>&1
```

**Windows (Task Scheduler):**

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" at 1:00 AM
4. Set action to "Start a program"
5. Program: `python`
6. Arguments: `-m backtester.services.update_runner`
7. Start in: `C:\path\to\atlas`

### Running Backtests

```bash
python main.py
```

## Monitoring

### Check Scheduler Status (Docker)

```bash
docker-compose ps scheduler
docker-compose logs --tail=100 scheduler
```

### Check Data Freshness

```bash
# View manifest
cat data/.cache_manifest.json | jq

# Or in Python
python -c "from backtester.data.cache_manager import load_manifest; import json; print(json.dumps(load_manifest(), indent=2))"
```

### Check Logs

```bash
# Daily update summary
tail -f artifacts/logs/daily_update.log

# Errors
tail -f artifacts/logs/fetch_errors.log

# Validation issues
tail -f artifacts/logs/data_validation.log
```

## Troubleshooting

### Scheduler Not Running

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs scheduler

# Restart scheduler
docker-compose restart scheduler
```

### Missing Data

1. **Check if market exists:**
```bash
python scripts/data/refetch_market.py BTC/USD 1h
```

2. **Check logs for errors:**
```bash
cat artifacts/logs/fetch_errors.log
```

3. **Manually re-fetch:**
```bash
python scripts/data/refetch_market.py BTC/USD 1h --force
```

### Cache Corruption

If cache files become corrupted:

```bash
# Delete specific market cache
rm data/BTC_USD_1h.csv

# Re-fetch
python scripts/refetch_market.py BTC/USD 1h
```

### Out of Disk Space

Monitor cache directory size:

```bash
du -sh data/
```

Cache files grow over time. For 85 markets × 8 timeframes:
- ~1MB per day of 1-minute data
- ~50KB per day of hourly data
- ~2KB per day of daily data

### Performance Issues

1. **Reduce update frequency** (modify scheduler schedule)
2. **Filter markets** in `exchange_metadata.yaml`
3. **Use longer timeframes** (1h, 1d instead of 1m, 5m)

## Production Recommendations

1. **Run scheduler in Docker** for reliability and auto-restart
2. **Monitor disk usage** - cache grows over time
3. **Set up log rotation** for log files
4. **Backup cache directory** periodically
5. **Use alerts** for scheduler failures (monitor logs)
6. **Schedule bulk re-fetch** quarterly to fix any gaps

## Cloud Deployment

### AWS ECS / Google Cloud Run

1. Build and push Docker image to container registry
2. Deploy as scheduled task/cron job
3. Use persistent volumes or object storage (S3/GCS) for cache

### Kubernetes

1. Create CronJob for daily updates
2. Use PersistentVolumeClaim for cache storage
3. Configure resource limits based on memory profiling

