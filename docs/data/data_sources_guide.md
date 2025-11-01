# Third-Party Data Sources Guide

## Purpose

How to integrate external data (e.g., on-chain, sentiment, news) using the `DataSourceProvider` abstraction. Data is aligned to OHLCV timeframes and joined before backtests.

## Interface Overview

- Base class: `backtester.data.sources.base.DataSourceProvider`
- Required methods:
  - `fetch(symbol: str, start_date: str, end_date: str) -> pd.DataFrame`
  - `get_column_names() -> List[str]`
- Optional:
  - `align_to_ohlcv(source_df, ohlcv_df, prefix='') -> pd.DataFrame` (default forward-fill)

## Quick Start

```python
from backtester.data.sources.onchain import MockOnChainProvider

provider = MockOnChainProvider()
raw = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')
aligned = provider.align_to_ohlcv(raw, ohlcv_df, prefix='onchain_')
enriched = ohlcv_df.join(aligned)
```

## Strategy Usage

```python
from backtester.strategies.base_strategy import BaseStrategy
from backtester.data.sources.onchain import MockOnChainProvider

class MyStrategy(BaseStrategy):
    @classmethod
    def get_required_data_sources(cls):
        return [MockOnChainProvider()]
```

## Implementing a Provider

```python
from backtester.data.sources.base import DataSourceProvider
import pandas as pd

class MyDataSource(DataSourceProvider):
    def fetch(self, symbol, start_date, end_date):
        # Return DataFrame indexed by datetime with your columns
        return pd.DataFrame({
            'datetime': pd.date_range(start_date, end_date, freq='D'),
            'my_metric': [1]*31,
        }).set_index('datetime')

    def get_column_names(self):
        return ['my_metric']
```

## Alignment Behavior

- Lower → higher frequency: forward-fill
- Initial gaps: back-fill then fill 0
- Columns prefixed when `prefix` provided (e.g., `onchain_my_metric`)

## References

- Base class: `src/backtester/data/sources/base.py`
- Mock provider: `src/backtester/data/sources/onchain.py`
