# Backtesting Engine - Product Requirements Document

## Project Overview

Build a basic cryptocurrency backtesting engine to test and evaluate trading strategies on historical data before risking capital in live trading.

## Goals & Objectives

### Primary Goals
- Enable rapid testing of crypto trading strategies on historical data
- Provide clear performance metrics to evaluate strategy effectiveness
- Support integration with multiple cryptocurrency exchanges via ccxt
- Offer a simple, extensible framework for strategy development

### Secondary Goals
- Generate visual performance reports
- Support paper trading capabilities
- Facilitate quick iteration on strategy ideas

## Target Users

**Primary:** Individual traders developing their own crypto strategies  
**Secondary:** Analysts testing quantitative approaches to cryptocurrency trading

## Core Features

### Phase 1: MVP (Minimum Viable Product)

#### 1. Data Management
- **Historical Data Fetching**
  - Connect to exchanges via ccxt (Binance, Coinbase Pro, etc.)
  - Fetch OHLCV (Open, High, Low, Close, Volume) data
  - Support multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)
  - Cache data locally to reduce API calls

- **Data Loading**
  - Load historical data from CSV files (optional alternative to API)
  - Data validation and cleaning
  - Handle missing data and gaps

#### 2. Strategy Framework
- **Backtrader Integration**
  - Define custom strategy classes
  - Built-in indicator library access (SMA, EMA, RSI, MACD, etc.)
  - Support for multiple position sizing methods (fixed, percentage, Kelly)

- **Strategy Components**
  - Entry conditions
  - Exit conditions
  - Stop loss and take profit levels
  - Position sizing rules

#### 3. Backtesting Engine
- **Execution**
  - Simulate trades on historical data
  - Track positions, orders, and P&L
  - Handle slippage and transaction costs (configurable)
  - Support for both long and short positions

- **Performance Metrics**
  - Total return (%)
  - Sharpe ratio
  - Maximum drawdown
  - Win rate (%)
  - Number of trades
  - Average win/loss ratio
  - Profit factor

#### 4. Reporting & Visualization
- **Performance Reports**
  - Console output with key metrics
  - CSV export of trade history
  - Equity curve visualization

- **Charts** (via Backtrader)
  - Price chart with indicators
  - Trade entry/exit markers
  - Volume bars

#### 5. Configuration
- **YAML Configuration**
  - Strategy parameters
  - Exchange and symbol selection
  - Date range for backtesting
  - Commission/slippage settings
  - Initial capital

### Phase 2: Future Enhancements (Out of Scope for MVP)

- Portfolio backtesting (multiple symbols)
- Machine learning strategy integration
- Paper trading module
- Strategy optimization (parameter tuning)
- Walk-forward analysis
- Monte Carlo simulation
- Live trading integration

## Technical Requirements

### Technology Stack

**Core Libraries:**
- **Python 3.8+**
- **ccxt** - Exchange API integration (primary exchange: Coinbase)
- **backtrader** - Backtesting framework
- **pandas** - Data manipulation
- **numpy** - Numerical operations
- **pyyaml** - Configuration management
- **matplotlib** - Visualization (via backtrader)

**Optional Libraries:**
- **yfinance** - Alternative data source for comparison
- **ta** - Technical analysis library (additional indicators)
- **plotly** - Enhanced visualizations

### Configuration Specifications

**Primary Exchange:** Coinbase (Advanced Trade)
- **Trading Pair:** BTC/USD (or other USD pairs)
- **Historical Data Range:** January 1, 2017 - Present
- **Commission Rate:** 0.5% per trade (taker fees, Coinbase Advanced Trade standard)

**Risk Management:**
- **Default Risk Per Trade:** 1% of account capital
- Position sizing and stop loss calculations based on this risk parameter
- Configurable per strategy via YAML config

**Default Backtest Settings:**
- **Initial Capital:** $10,000 USD
- **Timeframe:** 1-hour candles
- **Slippage:** 0.05% (0.0005)

### Project Structure

```
backtester-mvp/
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py
│   └── sma_cross.py (example)
├── data/
│   ├── fetch_data.py
│   ├── cache/
│   └── raw/
├── backtest/
│   ├── engine.py
│   └── metrics.py
├── config/
│   └── config.yaml
├── reports/
│   ├── trades.csv
│   └── performance.txt
├── requirements.txt
├── README.md
└── PRD.md
```

### Non-Functional Requirements

- **Performance:** Backtest 1 year of hourly data in < 30 seconds
- **Reliability:** Handle data gaps and missing candles gracefully
- **Usability:** Simple CLI interface for running backtests
- **Extensibility:** Easy to add new strategies
- **Maintainability:** Clean, documented code

## Success Criteria

### MVP Success Metrics
- Successfully backtest at least 3 different strategies
- Generate accurate performance metrics
- Produce readable reports and charts
- Execute in < 1 hour of development time per strategy

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API rate limits from exchanges | High | Medium | Implement caching, use local CSV files |
| Incorrect simulation logic | High | Low | Thorough testing with known strategies |
| Performance issues with large datasets | Medium | Low | Use pandas optimization, consider data chunking |
| Library compatibility issues | Low | Medium | Pin specific versions in requirements.txt |

## Dependencies & Constraints

**Constraints:**
- Must use Python
- Must integrate with ccxt for data
- Must use backtrader framework
- Limited to crypto assets (initially)

**Assumptions:**
- User has basic Python knowledge
- Internet connection for data fetching
- Focus on spot trading only (no futures/options initially)

## Next Steps

1. Set up project structure and dependencies
2. Implement data fetching module with ccxt
3. Create base strategy framework
4. Build backtesting engine using backtrader
5. Develop reporting and visualization
6. Test with sample strategies
7. Document usage and examples

## Open Questions (To Be Resolved)

- [ ] Preferred cryptocurrency exchanges?
- [ ] Specific timeframes to prioritize?
- [ ] Any particular indicators to support first?
- [ ] Commission/slippage assumptions for simulations?
- [ ] Target initial capital for simulations?
- [ ] Data caching strategy (database vs files)?

