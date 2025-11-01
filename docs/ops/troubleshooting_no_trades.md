# Troubleshooting: No Trades Generated

## Problem

Strategies complete backtests but show 0 trades and 0% return, even when there should be trading signals.

## Root Causes

### 1. Insufficient Capital (Most Common)

**Symptoms:**
- Strategy logs show "INSUFFICIENT CASH" messages
- Buy signals detected but size = 0
- Trades: 0

**Cause:**
The strategies calculate position size as:
```python
size = int((cash * 0.9) / price)
```

For high-priced assets like BTC (~$110,000):
- With $10,000 capital: `int((10000 * 0.9) / 110000) = int(0.08) = 0`
- Size rounds down to 0, so no trade executes

**Solution:**
Use sufficient capital for the asset price:
```python
# Calculate minimum capital needed
current_price = df['close'].iloc[-1]
min_capital = current_price * 1.2  # Enough for 1 BTC + buffer
config.config['backtest']['initial_capital'] = min_capital
```

**Recommended capital by asset:**
- BTC/USD: ~$120,000+ (for 1 BTC)
- ETH/USD: ~$3,000+ (for 1 ETH)
- Lower-priced assets: $10,000 is usually sufficient

### 2. Strategy Conditions Not Met

**Symptoms:**
- No "INSUFFICIENT CASH" messages
- Indicators computed correctly
- RSI/SMA values available
- But no trades

**Causes:**

#### SMACross Strategy
- Requires fast SMA to cross above/below slow SMA
- If market is trending strongly, no crossovers occur
- **Solution:** Use smaller periods (e.g., 10/20 instead of 20/50) for more signals

#### RSISMA Strategy  
- Requires: `RSI < 30 AND price > SMA` for buy
- This is a very strict condition (oversold during uptrend)
- **Diagnosis:** Run diagnostic script to see:
  - How many times RSI < 30 occurred
  - How many times price > SMA during those periods
  - Result: Often 0 because oversold usually happens during downtrends

**Solutions:**
- **Option A:** Use more historical data (different market conditions)
- **Option B:** Relax strategy parameters:
  - Lower RSI oversold threshold (e.g., 25 instead of 30)
  - Remove the `price > SMA` condition (buy on oversold alone)
  - Change logic: Buy when RSI < 30 regardless of trend

### 3. Insufficient Data Period

**Symptoms:**
- Very few candles (< 100)
- Indicators show mostly NaN values
- Strategy skips most bars

**Cause:**
Indicators need warm-up period:
- SMA(20) needs 20 bars before first value
- SMA(50) needs 50 bars before first value
- RSI(14) needs 14 bars before first value

**Solution:**
Use at least 100-200 candles, preferably 500+ for reliable results.

## Diagnostic Tools

### Run Diagnostic Script

```bash
python scripts/diagnose_no_trades.py
```

This shows:
- Market conditions (price range, RSI range)
- Number of crossover signals
- Number of RSI oversold/overbought periods
- Whether strategy conditions are being met
- Sample data with indicator values

### Test with Verbose Output

```bash
# Edit test script to set verbose=True
python scripts/test_single_market.py
```

Or modify config:
```python
config.config['backtest']['verbose'] = True
result = run_backtest(config, df, strategy_class, verbose=True)
```

This shows:
- Strategy log messages
- "INSUFFICIENT CASH" warnings
- Buy/sell signal attempts

## Testing Best Practices

### 1. Use Appropriate Capital

```python
# Calculate based on current price
current_price = df['close'].iloc[-1]
min_capital = current_price * 1.2  # For 1 unit + buffer
```

### 2. Use Sufficient Data

```python
# At least 500 candles for reliable indicators
if len(df) > 1000:
    df = df.tail(1000)  # Good
# Or use full dataset for realistic results
```

### 3. Test Different Time Periods

Some periods have more trading opportunities:
```python
# Test different date ranges
# Trending periods: fewer crossovers
# Volatile periods: more RSI signals
```

### 4. Adjust Strategy for Market Conditions

- **Trending markets:** Use trend-following strategies (SMACross works well)
- **Ranging markets:** Use mean-reversion strategies (RSI-based)
- **Volatile markets:** More signals, but also more false signals

## Example: Fixed Test Script

The `test_single_market.py` script has been updated to:
1. Calculate appropriate capital based on asset price
2. Show what capital is being used
3. Still test both strategies correctly

## Summary

**Most common issue:** Insufficient capital causing size calculations to round to 0.

**Quick fix:** Use capital >= current_price * 1.2 for high-priced assets.

**If still no trades:** Market conditions may not meet strategy criteria (this is correct behavior - strategy is working, just no signals).
