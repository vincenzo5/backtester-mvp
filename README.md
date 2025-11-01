# Crypto Backtesting Engine
Atlas — Automated Trading Logic & Strategy Analysis System

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
./scripts/deployment/start.sh
```

Or on Windows:
```powershell
.\scripts\deployment\start.ps1
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
1. Build: `cd deployment && docker-compose build`
2. Initial fetch: `cd deployment && docker-compose run --rm bulk-fetch`
3. Start scheduler: `cd deployment && docker-compose up -d scheduler`

### Manual Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Fetch exchange metadata (optional):
   ```bash
   python scripts/setup/fetch_exchange_info.py
   ```
   This creates `config/exchange_metadata.yaml` with:
   - Supported timeframes
   - Top trading markets
   - Maker/taker fee rates

3. **Initial data collection:**
   ```bash
   python scripts/data/bulk_fetch.py
   ```
   This fetches all historical data back to 2017 (or earliest available) for all markets/timeframes.

4. **Install package** (required for imports):
   ```bash
   pip install -e .
   ```

5. **Setup daily updates** (optional):
   ```bash
   # Run manually
   python -m backtester.services.update_runner
   
   # Or start scheduler daemon
   python -m backtester.services.scheduler_daemon
   ```

6. Run backtests:
   ```bash
   python main.py
   ```

## Project Structure

```
atlas/
├── src/
│   └── backtester/      # Main package (backtest, cli, config, data, indicators, strategies, services)
├── tests/               # Test suite
├── scripts/             # Utility scripts organized by purpose
│   ├── data/           # Data collection scripts
│   ├── diagnostics/    # Diagnostic tools
│   ├── setup/          # Setup/utility scripts
│   ├── deployment/     # Deployment scripts (start.sh, start.ps1)
│   └── tests/          # Standalone test scripts
├── config/             # Configuration files (YAML)
├── data/               # Data cache and storage
├── docs/               # Documentation
├── artifacts/          # Runtime-generated files
│   ├── logs/          # Application logs
│   ├── reports/        # Generated reports and charts
│   └── performance/    # Performance metrics
├── deployment/          # Docker configuration
│   ├── Dockerfile
│   └── docker-compose.yml
├── main.py             # Entry point
├── pyproject.toml      # Modern Python packaging config
└── requirements.txt    # Dependencies (legacy, use pyproject.toml)
```

## Data Collection

The system includes an automated data collection pipeline:

- **Smart Delta Updates**: Only fetches new candles since last update
- **Validation**: Detects gaps and duplicates automatically
- **Auto-cleanup**: Removes invalid markets from metadata
- **Docker-ready**: Containerized for easy deployment

See [docs/data/data_pipeline.md](docs/data/data_pipeline.md) for detailed information.

## Deployment

For production deployment, see [docs/setup/deployment.md](docs/setup/deployment.md).

### Key Features:
- Docker containerization for portability
- Automated daily updates via scheduler daemon
- Persistent data storage via volumes
- Configurable update schedules

## Documentation

- [Data Pipeline Guide](docs/data/data_pipeline.md) - How data collection works
- [Deployment Guide](docs/setup/deployment.md) - Docker and manual deployment
- [CI/CD Overview](docs/setup/ci_cd.md) - Workflow, runner, and image publishing
- [Configuration Reference](docs/config/configuration_reference.md) - Domain YAMLs and typed accessors
- [Walk-Forward & Filters Guide](docs/strategies/walkforward_guide.md) - Walk-forward usage and filters
- [Debugging & Tracing](docs/ops/debugging_and_tracing.md) - Tracer and crash reporter
- [Performance Attribution](docs/metrics/performance_attribution.md) - Where and how metrics are logged
- [Interface Contract](docs/overview/interface_contract.md) - Stable cache API

## Development Safety

The cache system maintains a **stable interface contract** between data collection and backtesting systems. This allows you to:

- ✅ Run data collection scheduler continuously while developing backtest logic
- ✅ Update backtest code without affecting running data collection
- ✅ Share improvements across both systems

See [Interface Contract](docs/overview/interface_contract.md) for details. Run compatibility tests:

```bash
pytest tests/test_cache_compatibility.py -v
```

## Status

🚧 In Development - MVP Phase

