# Data Pipeline Documentation

## Overview

The data collection system provides automated fetching, caching, and updating of historical cryptocurrency OHLCV data. It uses a **smart delta update** strategy to efficiently maintain up-to-date datasets with minimal API calls.

## Architecture

### Components

1. **Data Modules** (`data/`)
   - `cache_manager.py` - File I/O and manifest tracking
   - `fetcher.py` - Core CCXT fetching logic
   - `validator.py` - Data validation (gaps, duplicates)
   - `updater.py` - Smart delta update orchestration

2. **Services** (`services/`)
   - `update_runner.py` - Daily delta update service
   - `scheduler_daemon.py` - Background scheduler for automated updates

3. **Scripts** (`scripts/`)
   - `bulk_fetch.py` - Initial historical data collection
   - `refetch_market.py` - Manual re-fetch utility
   - `migrate_cache.py` - Cache file migration tool

## Data Flow

### Initial Data Collection

```
bulk_fetch.py
    ↓
Read exchange_metadata.yaml (markets, timeframes)
    ↓
For each market/timeframe:
    ↓
Check if cache exists → Skip if found
    ↓
Fetch from exchange (2017-01-01 to today)
    ↓
Validate data (gaps, duplicates)
    ↓
Save to cache (BTC_USD_1h.csv)
    ↓
Update manifest (.cache_manifest.json)
```

### Daily Updates

```
scheduler_daemon.py (runs daily at 1 AM UTC)
    ↓
update_runner.py
    ↓
Read manifest → Find last cached timestamp
    ↓
For each market/timeframe:
    ↓
Check if update needed (cache > 1 day old)
    ↓
Fetch only new candles since last timestamp
    ↓
Validate and append to existing cache
    ↓
Update manifest
```

## Cache Structure

### File Naming

**New format (simplified):**
```
data/cache/
├── BTC_USD_1h.csv
├── ETH_USD_1d.csv
└── .cache_manifest.json
```

**Old format (legacy):**
```
data/cache/
└── BTC_USD_1h_2017-01-01_2025-10-27.csv  # Deprecated
```

### Manifest

The `.cache_manifest.json` file tracks metadata:

```json
{
  "BTC_USD_1h": {
    "symbol": "BTC/USD",
    "timeframe": "1h",
    "first_date": "2015-01-01",
    "last_date": "2025-10-28",
    "candle_count": 94824,
    "last_updated": "2025-10-28T01:00:00Z"
  }
}
```

## Smart Delta Update

### How It Works

1. **Check Last Timestamp**: Read manifest or cache file to find last cached candle
2. **Calculate Delta**: Fetch only candles after last timestamp
3. **Append**: Combine new data with existing cache (remove duplicates)
4. **Validate**: Check for gaps and data quality issues
5. **Update Manifest**: Record new last_date and candle_count

### Benefits

- **99.9% reduction in API calls** after initial fetch
- **Fast updates**: 1 day of data takes seconds instead of minutes
- **Accumulative**: Historical data grows indefinitely
- **Efficient**: Only fetches what's needed

## Validation

### Gap Detection

Detects missing candles in timeseries:
- Compares actual intervals vs expected timeframe intervals
- Logs gaps to `logs/data_validation.log`
- Still appends partial data (better than nothing)

### Duplicate Removal

- Removes duplicate timestamps (keeps last occurrence)
- Handles overlapping data from API
- Ensures data integrity

## Error Handling

### Market Not Found

If exchange returns "market not found":
1. Log error to `logs/fetch_errors.log`
2. Remove market from `exchange_metadata.yaml`
3. Continue with other markets

### Network Errors

- Temporary failures are logged
- Can be retried manually with `refetch_market.py`
- Scheduler will retry on next scheduled run

## Configuration

### Historical Start Date

Set in `config.yaml`:
```yaml
data:
  historical_start_date: "2017-01-01"  # Configurable
```

### Update Schedule

Set via environment variables or in `scheduler_daemon.py`:
- Default: 1:00 AM UTC daily
- Configurable via `UPDATE_HOUR` and `UPDATE_MINUTE` env vars

## Usage

### Initial Setup

```bash
# Fetch all historical data
python scripts/bulk_fetch.py

# Or with Docker
docker-compose run --rm bulk-fetch
```

### Daily Updates

```bash
# Run manually
python services/update_runner.py

# Or start scheduler daemon
python services/scheduler_daemon.py

# Or with Docker
docker-compose up -d scheduler
```

### Manual Re-fetch

```bash
# Re-fetch specific market
python scripts/refetch_market.py BTC/USD 1h

# With force flag (delete existing cache)
python scripts/refetch_market.py BTC/USD 1h --force
```

### Migration

```bash
# Migrate old cache files to new format
python scripts/migrate_cache.py
```

## Monitoring

### Log Files

- `logs/daily_update.log` - Update summary and progress
- `logs/fetch_errors.log` - API errors and failures
- `logs/data_validation.log` - Data quality issues (gaps, duplicates)

### Performance Metrics

- `performance/fetch_performance.jsonl` - Fetch timing and statistics
- JSON Lines format for easy parsing

## Best Practices

1. **Run initial bulk fetch** before using backtest system
2. **Keep scheduler running** for automatic updates
3. **Monitor logs** for data quality issues
4. **Use refetch_market.py** to fix corrupted data
5. **Check manifest** for data coverage information

