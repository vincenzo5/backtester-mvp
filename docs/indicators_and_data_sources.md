# Indicators and Third-Party Data Sources

This document explains the indicator library and third-party data source abstractions in the backtesting system.

## Overview

The backtesting system now supports two powerful abstraction layers:

1. **Indicator Library**: Pre-computed technical indicators (TA-Lib + custom)
2. **Data Source Providers**: Third-party data that gets aligned to OHLCV timeframes

Both are designed for **pre-computation** before backtests run, making them optimal for walk-forward optimization where the same indicators/data are reused across many parameter combinations.

## Architecture

```
┌─────────────────┐
│   OHLCV Data    │
│   (DataFrame)   │
└────────┬────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
┌──────────────────┐           ┌──────────────────────┐
│ Indicator Library │           │ Data Source Providers│
│  - TA-Lib wrappers│           │  - On-chain metrics  │
│  - Custom inds    │           │  - Sentiment data    │
│  - Batch compute  │           │  - News feeds        │
└────────┬─────────┘           └──────────┬───────────┘
         │                                 │
         │                                 │
         └────────┬───────────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ Enriched        │
        │ DataFrame       │
        │ (OHLCV +        │
        │  Indicators +   │
        │  External Data) │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │   Backtest      │
        │   Engine        │
        └─────────────────┘
```

## Indicator Library

### Quick Start

```python
from indicators import IndicatorLibrary, IndicatorSpec

# Create library
lib = IndicatorLibrary()

# Define indicators
specs = [
    IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
    IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
]

# Compute and add to DataFrame
enriched_df = lib.compute_all(df, specs)
```

### Supported Indicators

Built-in indicators (wrapping `ta` library):

- **SMA**: Simple Moving Average
- **EMA**: Exponential Moving Average
- **RSI**: Relative Strength Index
- **MACD**: Moving Average Convergence Divergence (returns 3 columns: macd, signal, hist)
- **BBANDS**: Bollinger Bands (returns 3 columns: upper, middle, lower)

### Using Indicators in Strategies

Strategies declare required indicators via the `get_required_indicators()` classmethod:

```python
from strategies.base_strategy import BaseStrategy
from indicators.base import IndicatorSpec

class MyStrategy(BaseStrategy):
    @classmethod
    def get_required_indicators(cls, params):
        return [
            IndicatorSpec('SMA', {'timeperiod': params['fast_period']}, 'SMA_fast'),
            IndicatorSpec('SMA', {'timeperiod': params['slow_period']}, 'SMA_slow'),
            IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
        ]
    
    def next(self):
        # Access pre-computed indicators
        sma_fast = self.data.SMA_fast[0]
        sma_slow = self.data.SMA_slow[0]
        rsi = self.data.RSI_14[0]
        
        # Your trading logic here
        if sma_fast > sma_slow and rsi < 70:
            self.buy()
```

### Creating Custom Indicators

Register custom indicator functions:

```python
from indicators.base import register_custom_indicator
import pandas as pd

def my_volume_indicator(df, params):
    """Average volume over last N periods"""
    return df['volume'].rolling(window=params['period']).mean()

# Register it
register_custom_indicator('AVG_VOLUME', my_volume_indicator)

# Now use it like any built-in indicator
from indicators.base import IndicatorSpec
spec = IndicatorSpec('AVG_VOLUME', {'period': 10}, 'avg_vol_10')
```

Custom indicator functions must:
- Take `(df: pd.DataFrame, params: dict)` as arguments
- Return `pd.Series` or `pd.DataFrame`
- Work with OHLCV columns: `open`, `high`, `low`, `close`, `volume`

### Multi-Column Indicators

Some indicators return multiple columns (e.g., MACD, Bollinger Bands). They're automatically named with a prefix:

```python
IndicatorSpec('MACD', {...}, 'MACD')
# Results in columns:
# - MACD_macd
# - MACD_signal
# - MACD_hist

IndicatorSpec('BBANDS', {...}, 'BB')
# Results in columns:
# - BB_upper
# - BB_middle
# - BB_lower
```

## Third-Party Data Sources

### Quick Start

```python
from data.sources.onchain import MockOnChainProvider

# Create provider
provider = MockOnChainProvider()

# Fetch data
raw_data = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')

# Align to OHLCV timeframe
aligned_data = provider.align_to_ohlcv(raw_data, ohlcv_df, prefix='onchain_')
```

### Using Data Sources in Strategies

Strategies declare required data sources via `get_required_data_sources()`:

```python
from strategies.base_strategy import BaseStrategy
from data.sources.onchain import MockOnChainProvider

class MyStrategy(BaseStrategy):
    @classmethod
    def get_required_data_sources(cls):
        return [MockOnChainProvider()]
    
    def next(self):
        # Access aligned data (prefixed with provider name)
        active_addresses = self.data.onchain_active_addresses[0]
        tx_count = self.data.onchain_tx_count[0]
        
        if active_addresses > 1000000:
            # High network activity signal
            self.buy()
```

### Creating Custom Data Source Providers

Implement the `DataSourceProvider` interface:

```python
from data.sources.base import DataSourceProvider
import pandas as pd

class MyDataSource(DataSourceProvider):
    def fetch(self, symbol, start_date, end_date):
        """Fetch raw data from your source"""
        # Call API, read file, query database, etc.
        return pd.DataFrame({
            'datetime': pd.date_range(start_date, end_date, freq='D'),
            'my_metric': [...],
        }).set_index('datetime')
    
    def get_column_names(self):
        """Return column names this provider adds"""
        return ['my_metric']
```

The provider will automatically:
- Have its data aligned to OHLCV timeframe (forward-fill for lower frequency)
- Get columns prefixed with provider name (e.g., `mydatasource_my_metric`)

### Alignment Behavior

Data sources are automatically aligned to OHLCV timeframes:

- **Lower frequency → Higher frequency**: Forward-fill (daily → hourly: each hour gets the day's value)
- **Higher frequency → Lower frequency**: Last value per period (not yet implemented)
- **Missing values**: Forward-filled, then back-filled, then filled with 0

Example: Daily on-chain data aligned to hourly candles:
```
Daily Data:
2024-01-01: active_addresses=1000000
2024-01-02: active_addresses=1050000

Hourly OHLCV:
2024-01-01 00:00 → 1000000 (forward-filled)
2024-01-01 01:00 → 1000000 (forward-filled)
...
2024-01-02 00:00 → 1050000 (forward-filled)
```

## Integration with Backtest Engine

The backtest engine automatically handles indicators and data sources:

1. Strategy declares requirements (`get_required_indicators()`, `get_required_data_sources()`)
2. Engine pre-computes all indicators
3. Engine fetches and aligns all data sources
4. Enriched DataFrame passed to backtrader
5. Strategy accesses pre-computed values via `self.data` in `next()`

No changes needed to existing code - old strategies (like `sma_cross`) continue to work.

## Walk-Forward Optimization

The pre-computation design is optimized for walk-forward optimization:

```python
# Prepare data once (expensive operation)
base_df = load_ohlcv_data()
strategy_class = MyStrategy
base_params = {'fast_period': 20, 'slow_period': 50}

# Compute indicators once
enriched_df = prepare_backtest_data(base_df, strategy_class, base_params)

# Run many backtests quickly (reusing pre-computed indicators)
for params in parameter_combinations:
    result = run_backtest(config, enriched_df, strategy_class, verbose=False)
```

All indicators are computed once and reused across parameter combinations, dramatically speeding up optimization.

## Examples

### Example 1: Simple Indicator Strategy

```python
class SimpleRSIStrategy(BaseStrategy):
    @classmethod
    def get_required_indicators(cls, params):
        return [IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14')]
    
    def next(self):
        rsi = self.data.RSI_14[0]
        if rsi < 30:
            self.buy()
        elif rsi > 70:
            self.sell()
```

### Example 2: Combining Indicators and Data

```python
class OnChainRSIStrategy(BaseStrategy):
    @classmethod
    def get_required_indicators(cls, params):
        return [IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14')]
    
    @classmethod
    def get_required_data_sources(cls):
        return [MockOnChainProvider()]
    
    def next(self):
        rsi = self.data.RSI_14[0]
        addresses = self.data.onchain_active_addresses[0]
        
        # RSI oversold + high network activity = strong buy
        if rsi < 30 and addresses > 1500000:
            self.buy()
```

### Example 3: Custom Indicator

```python
from indicators.base import register_custom_indicator

def price_momentum(df, params):
    """Price change over N periods"""
    return (df['close'] - df['close'].shift(params['period'])) / df['close'].shift(params['period'])

register_custom_indicator('PRICE_MOMENTUM', price_momentum)

class MomentumStrategy(BaseStrategy):
    @classmethod
    def get_required_indicators(cls, params):
        return [IndicatorSpec('PRICE_MOMENTUM', {'period': 10}, 'momentum_10')]
    
    def next(self):
        momentum = self.data.momentum_10[0]
        if momentum > 0.05:  # 5% gain in 10 periods
            self.buy()
```

## Adding New Built-in Indicators

To add support for a new `ta` library indicator:

1. Import the indicator class in `indicators/library.py`
2. Add a case in `_compute_ta_indicator()` method
3. Handle parameters and return Series/DataFrame

Example:
```python
elif indicator_type == 'STOCH':
    from ta.momentum import StochasticOscillator
    indicator = StochasticOscillator(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=params.get('timeperiod', 14)
    )
    return pd.DataFrame({
        'stoch': indicator.stoch(),
        'stoch_signal': indicator.stoch_signal()
    })
```

## Performance Considerations

- **Pre-computation**: All indicators computed once before backtest (not per-bar)
- **Batch processing**: Multiple indicators computed efficiently in one pass
- **Walk-forward**: Same indicators reused across parameter combinations
- **Memory**: Enriched DataFrame stored in memory (acceptable trade-off for speed)

For very large datasets or many indicators, consider:
- Computing indicators on-demand (future enhancement)
- Using lazy evaluation for expensive indicators
- Caching indicator results to disk

## Future Enhancements

Potential additions:
- More TA-Lib indicators
- Custom alignment strategies (interpolation, aggregation)
- Indicator caching to disk
- Parallel indicator computation
- Real-time indicator updates (for live trading)
- Multiple timeframes support
- Indicator dependencies (indicator of indicators)
