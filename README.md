# Crypto Backtesting Engine

A simple but powerful cryptocurrency backtesting engine built with Python, ccxt, and backtrader.

## Overview

This project provides a framework for backtesting trading strategies on historical cryptocurrency data. It integrates with multiple exchanges via ccxt and uses backtrader for simulation and analysis.

## Features

- 📊 Fetch historical data from major crypto exchanges
- 🔄 Backtest trading strategies with customizable parameters
- 📈 Calculate performance metrics (Sharpe ratio, drawdown, win rate, etc.)
- 📉 Visualize results with charts and equity curves
- ⚙️ YAML-based configuration for easy experimentation

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Using Docker (Recommended)

**Single command startup:**
```bash
./scripts/start.sh
```

Or on Windows:
```powershell
.\scripts\start.ps1
```

This will:
- Build the Docker image (if needed)
- Offer to run initial data collection (if cache is empty)
- Start the scheduler daemon for daily updates
- Show status and useful commands

**Note:** Data collection runs in Docker, but backtests run directly on your host:
```bash
python main.py  # Run backtests locally for development
```

**Manual steps (if preferred):**
1. Build: `docker-compose build`
2. Initial fetch: `docker-compose run --rm bulk-fetch`
3. Start scheduler: `docker-compose up -d scheduler`

### Manual Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Fetch exchange metadata (optional):
   ```bash
   python scripts/fetch_exchange_info.py
   ```
   This creates `config/exchange_metadata.yaml` with:
   - Supported timeframes
   - Top trading markets
   - Maker/taker fee rates

3. **Initial data collection:**
   ```bash
   python scripts/bulk_fetch.py
   ```
   This fetches all historical data back to 2017 (or earliest available) for all markets/timeframes.

4. **Setup daily updates** (optional):
   ```bash
   # Run manually
   python services/update_runner.py
   
   # Or start scheduler daemon
   python services/scheduler_daemon.py
   ```

5. Run backtests:
   ```bash
   python main.py
   ```

## Project Structure

```
backtester-mvp/
├── strategies/      # Trading strategies
├── data/            # Data modules (fetcher, cache_manager, validator, updater)
├── services/        # Background services (scheduler, update_runner)
├── scripts/         # Utility scripts (bulk_fetch, refetch_market)
├── backtest/        # Backtesting engine
├── config/          # Configuration files
├── reports/         # Generated reports and charts
├── logs/            # Application logs
└── requirements.txt # Dependencies
```

## Data Collection

The system includes an automated data collection pipeline:

- **Smart Delta Updates**: Only fetches new candles since last update
- **Validation**: Detects gaps and duplicates automatically
- **Auto-cleanup**: Removes invalid markets from metadata
- **Docker-ready**: Containerized for easy deployment

See [docs/data_pipeline.md](docs/data_pipeline.md) for detailed information.

## Deployment

For production deployment, see [docs/deployment.md](docs/deployment.md).

### Key Features:
- Docker containerization for portability
- Automated daily updates via scheduler daemon
- Persistent data storage via volumes
- Configurable update schedules

## Documentation

- [Data Pipeline Guide](docs/data_pipeline.md) - How data collection works
- [Deployment Guide](docs/deployment.md) - Docker and manual deployment
- [Interface Contract](docs/interface_contract.md) - Stable API for cache system compatibility

## Development Safety

The cache system maintains a **stable interface contract** between data collection and backtesting systems. This allows you to:

- ✅ Run data collection scheduler continuously while developing backtest logic
- ✅ Update backtest code without affecting running data collection
- ✅ Share improvements across both systems

See [Interface Contract](docs/interface_contract.md) for details. Run compatibility tests:

```bash
pytest tests/test_cache_compatibility.py -v
```

## Status

🚧 In Development - MVP Phase

