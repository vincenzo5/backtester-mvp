# Cache Interface Contract

## Purpose

This document defines the stable interface contract for the cache system, ensuring compatibility between the data collection system and the backtesting engine during parallel development.

## Stable API Contracts

### `data.cache_manager.read_cache()`

**Signature:** `read_cache(symbol: str, timeframe: str) -> pd.DataFrame`

**Must not change:**
- Function signature (parameters and return type)
- Return format (DataFrame with DatetimeIndex and OHLCV columns)
- Behavior (returns empty DataFrame if cache doesn't exist)

**Return format:**
```python
DataFrame with:
- Index: pd.DatetimeIndex (timezone-aware UTC)
- Columns: ['open', 'high', 'low', 'close', 'volume']
- Returns: Empty DataFrame if cache doesn't exist
```

### `data.cache_manager.write_cache()`

**Signature:** `write_cache(symbol: str, timeframe: str, df: pd.DataFrame)`

**Must not change:**
- Function signature
- CSV file format (datetime index + OHLCV columns)
- Writing behavior (overwrites existing file)

**Input requirements:**
- `df` must have `pd.DatetimeIndex`
- `df` must have columns: ['open', 'high', 'low', 'close', 'volume']

**File format:**
- CSV format readable by `pd.read_csv()`
- Index column named 'datetime'
- Columns: open, high, low, close, volume

## File Naming Convention

**Format:** `{SYMBOL}_{TIMEFRAME}.csv`
- Example: `BTC_USD_1h.csv`
- Symbol '/' replaced with '_'
- No date ranges in filename (simplified from old format)

**Location:** `data/`

## Cache File Format

**CSV Structure:**
```csv
datetime,open,high,low,close,volume
2025-01-01 00:00:00+00:00,100.0,105.0,95.0,102.0,1000.0
2025-01-01 01:00:00+00:00,101.0,106.0,96.0,103.0,1100.0
...
```

**Key properties:**
- Datetime index in ISO format with timezone (UTC)
- Numeric columns (float)
- No duplicates (last occurrence wins)
- Sorted chronologically

## Compatibility Guarantees

1. **Read compatibility:** Files written by any version must be readable by `read_cache()`
2. **Write compatibility:** Data written by `write_cache()` must follow CSV format above
3. **Backtest compatibility:** Filtered data (by date range) must work with backtest engine
4. **Append compatibility:** Delta updates append new data without modifying existing rows

## Breaking Changes

**DO NOT:**
- Change function signatures
- Change CSV column names or order
- Change datetime index format
- Remove columns from CSV format
- Change file naming convention

**ALLOWED:**
- Internal implementation changes (as long as interface stays same)
- Performance optimizations
- Additional functions/modules
- Bug fixes that maintain interface

## Testing

Run compatibility tests to ensure contract is maintained:

```bash
pytest tests/test_cache_compatibility.py -v
```

These tests verify:
- Write/read roundtrip integrity
- CSV format compliance
- Backtest filtering compatibility
- Append behavior (delta updates)

## Version History

- **v1.0** (2025-10-28): Initial stable interface
  - Simplified cache naming (no date ranges)
  - CSV format with datetime index
  - Manifest tracking introduced

