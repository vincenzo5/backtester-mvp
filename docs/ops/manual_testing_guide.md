# Manual Testing Guide

This guide shows you how to test the backtesting system manually.

## Quick Test (Single Market)

Configure via YAML (no CLI flags). Use `config/profiles/quick.yaml` and domain configs.

```bash
python main.py
```

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

Update `config/strategy.yaml`:

```yaml
strategy:
  name: sma_cross
```

Then run:

```bash
python main.py
```

### Test RSISMA Strategy (with indicators)

Update `config/strategy.yaml`:

```yaml
strategy:
  name: rsi_sma
```

Then run:

```bash
python main.py
```

## Testing Multiple Markets

Run backtests on all configured markets (from `config/markets.yaml` and `config/data.yaml`):

```bash
python main.py
```

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
artifacts/reports/backtest_<strategy_name>_<timestamp>.csv
```

You can open this CSV to see detailed results.

## Troubleshooting

### "No cached data found"

**Problem:** No data in cache for the requested symbol/timeframe.

**Solution:**
```bash
# Fetch data first
python scripts/data/bulk_fetch.py
```

### "Invalid comparison between datetime"

**Problem:** Timezone mismatch between cached data and date filtering.

**Status:** ✅ Fixed in `backtest/execution/parallel.py` - should not occur anymore.

If you see this, ensure you're on latest `main` and re-run.

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
