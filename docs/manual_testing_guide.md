# Manual Testing Guide

This guide shows you how to test the backtesting system manually.

## Quick Test (Single Market)

Test with a single market using the `--quick` flag:

```bash
python main.py --quick
```

This uses the `quick_test` configuration from `config.yaml`:
- Single symbol: BTC/USD
- Single timeframe: 1h
- Verbose output enabled

**Expected output:**
- Backtest runs successfully
- Results show return %, final value, number of trades
- No errors

## Custom Single Market Test

Use the test script to test with custom parameters:

```bash
python scripts/test_single_market.py
```

This tests:
- Data loading from cache
- Old strategy (SMACross) - backward compatibility
- New strategy (RSISMA) - with pre-computed indicators
- End-to-end flow verification

## Testing Different Strategies

### Test SMACross Strategy

```bash
# Edit config.yaml:
strategy:
  name: sma_cross
  parameters:
    fast_period: 20
    slow_period: 50

python main.py --quick
```

### Test RSISMA Strategy (with indicators)

```bash
# Edit config.yaml:
strategy:
  name: rsi_sma
  parameters:
    sma_period: 20
    rsi_period: 14
    rsi_oversold: 30
    rsi_overbought: 70

python main.py --quick
```

## Testing Multiple Markets

Run backtests on all configured markets:

```bash
python main.py
```

This uses the full `exchange` configuration from `config.yaml`.

## What to Check

### Successful Backtest Output

✅ **Good signs:**
- "Successful: 1" (or more)
- No "Failed" or "Error" messages
- Results show reasonable return percentages
- Execution time is reasonable (< 1s per market for quick test)

❌ **Problems:**
- "Failed: 1" or error messages
- "Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp" (should be fixed now)
- No results showing

### Indicator Computation

When using strategies with indicators (like `rsi_sma`), check:
- Data preparation message shows indicators added: "Prepared data: Added X columns"
- Indicator columns listed (e.g., "RSI_14, SMA_20")
- Backtest completes without errors accessing indicators

### Results Location

Results are saved to:
```
reports/backtest_<strategy_name>_<timestamp>.csv
```

You can open this CSV to see detailed results.

## Troubleshooting

### "No cached data found"

**Problem:** No data in cache for the requested symbol/timeframe.

**Solution:**
```bash
# Fetch data first
python scripts/bulk_fetch.py
```

### "Invalid comparison between datetime"

**Problem:** Timezone mismatch between cached data and date filtering.

**Status:** ✅ Fixed in `backtest/execution/parallel.py` - should not occur anymore.

If you see this, verify the fix was applied:
```python
# In backtest/execution/parallel.py, lines 57-63 should have:
if df.index.tz is not None:
    from datetime import timezone
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
```

### Strategy Not Found

**Problem:** Strategy name in config doesn't match registered strategies.

**Solution:** Check `strategies/__init__.py` for registered strategy names:
- `sma_cross` → SMACrossStrategy
- `rsi_sma` → RSISMAStrategy

## Advanced Testing

### Test with Real Cached Data

```bash
python scripts/test_end_to_end_indicators.py
```

Tests both strategies with real cached data and verifies indicators work.

### Test Indicator Library Directly

```bash
python scripts/test_indicators_and_sources.py
```

Tests indicator computation, data sources, and integration separately.

## Verification Checklist

After making changes, verify:

- [ ] `python main.py --quick` completes successfully
- [ ] Old strategy (sma_cross) still works
- [ ] New strategy (rsi_sma) works with indicators
- [ ] No datetime comparison errors
- [ ] Results CSV file is generated
- [ ] Execution time is reasonable
