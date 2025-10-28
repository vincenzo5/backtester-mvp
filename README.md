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

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Fetch exchange metadata for up-to-date fees and timeframes:
   ```bash
   python scripts/fetch_exchange_info.py
   ```
   This will create `config/exchange_metadata.yaml` with:
   - Supported timeframes
   - Top 50 trading markets
   - Maker/taker fee rates

3. Run the backtest:
   ```bash
   python main.py
   ```

4. The script will:
   - Fetch historical data from Coinbase (BTC/USD from 2017-2024)
   - Use dynamic exchange fees (or fallback to config)
   - Run the SMA crossover strategy
   - Display results and generate a plot

## Project Structure

```
backtester-mvp/
├── strategies/      # Your trading strategies
├── data/            # Historical data and caching
├── backtest/        # Backtesting engine
├── config/          # Configuration files
├── reports/         # Generated reports and charts
└── requirements.txt # Dependencies
```

## Documentation

See [PRD.md](PRD.md) for detailed requirements and specifications.

## Status

🚧 In Development - MVP Phase

