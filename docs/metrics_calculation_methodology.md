# Metrics Calculation Methodology

This document describes the calculation methods and formulas for all 43 metrics calculated in the backtester. All metrics follow MultiWalk's calculation methodology using mark-to-market equity curve data.

## Table of Contents

1. [Basic Metrics](#basic-metrics)
2. [Trade Statistics](#trade-statistics)
3. [Day Statistics](#day-statistics)
4. [Drawdown Metrics](#drawdown-metrics)
5. [Advanced Metrics](#advanced-metrics)
6. [Walk-Forward Specific Metrics](#walk-forward-specific-metrics)

---

## Basic Metrics

### 1. Net Profit (`net_profit`)
**Formula:** `Final Value - Initial Capital`

The total dollar profit or loss from the backtest.

### 2. Total Return Percentage (`total_return_pct`)
**Formula:** `(Net Profit / Initial Capital) × 100`

Percentage return on initial capital. Can be positive (profit) or negative (loss).

### 3. Sharpe Ratio (`sharpe_ratio`)
**Formula:** `(Mean Return - Risk-Free Rate) / Standard Deviation of Returns`

Calculated from the equity curve:
1. Compute period-by-period returns: `(Value[t] - Value[t-1]) / Value[t-1]`
2. Calculate mean return
3. Calculate standard deviation of returns
4. Sharpe = (mean - risk_free_rate) / std

**Note:** Risk-free rate defaults to 0.0. The ratio is not annualized for simplicity.

### 4. Maximum Drawdown (`max_drawdown`)
**Formula:** `Peak Value - Lowest Value After Peak`

The largest dollar decline from a peak equity value to the subsequent trough. Calculated by:
1. Finding all peaks in the equity curve
2. For each peak, finding the lowest value before the next peak
3. Taking the maximum of all peak-to-trough declines

### 5. Profit Factor (`profit_factor`)
**Formula:** `Gross Profit / Gross Loss`

Ratio of total gross profit to total gross loss. 
- If `gross_loss > 0`: `profit_factor = gross_profit / gross_loss`
- If `gross_loss == 0` and `gross_profit > 0`: `profit_factor = infinity`
- Otherwise: `profit_factor = 0.0`

### 6. NP/AvgDD (`np_avg_dd`)
**Formula:** `Net Profit / Average Drawdown`

Ratio of net profit to average drawdown.
- If `avg_drawdown > 0`: `np_avg_dd = net_profit / avg_drawdown`
- If `avg_drawdown == 0` and `net_profit > 0`: `np_avg_dd = infinity`
- Otherwise: `np_avg_dd = 0.0`

### 7. Gross Profit (`gross_profit`)
**Formula:** Sum of all positive trade P&L values

Total profit from all winning trades.

### 8. Gross Loss (`gross_loss`)
**Formula:** Absolute value of sum of all negative trade P&L values

Total loss from all losing trades (stored as positive value).

### 9. Number of Trades (`num_trades`)
**Formula:** Count of all executed trades

Total number of trade entries (buy signals that were executed).

### 10. Number of Winning Trades (`num_winning_trades`)
**Formula:** Count of trades with positive P&L

Total number of profitable trades.

### 11. Number of Losing Trades (`num_losing_trades`)
**Formula:** Count of trades with negative P&L

Total number of unprofitable trades.

### 12. Average Drawdown (`avg_drawdown`)
**Formula:** `Sum of All Drawdowns / Number of Drawdown Periods`

Average of all drawdown values in the equity curve. Calculated by:
1. Identifying all drawdown periods (declines from peaks)
2. Summing all drawdown values
3. Dividing by the number of drawdown periods

---

## Trade Statistics

### 13. Win Rate Percentage (`win_rate_pct`)
**Formula:** `(Number of Winning Trades / Total Trades) × 100`

Also known as percent trades profitable. Percentage of trades that were profitable.

### 14. Percent Trades Profitable (`percent_trades_profitable`)
**Formula:** Same as `win_rate_pct`

Alias for win rate percentage.

### 15. Percent Trades Unprofitable (`percent_trades_unprofitable`)
**Formula:** `(Number of Losing Trades / Total Trades) × 100`

Percentage of trades that were unprofitable.

### 16. Average Trade (`avg_trade`)
**Formula:** `Net Profit / Total Trades`

Average dollar amount per trade (can be positive or negative).

### 17. Average Profitable Trade (`avg_profitable_trade`)
**Formula:** `Gross Profit / Number of Winning Trades`

Average dollar amount of profitable trades. Zero if no winning trades.

### 18. Average Unprofitable Trade (`avg_unprofitable_trade`)
**Formula:** `Gross Loss / Number of Losing Trades`

Average dollar amount of losing trades (negative value). Zero if no losing trades.

### 19. Largest Winning Trade (`largest_winning_trade`)
**Formula:** Maximum of all positive trade P&L values

The single largest profit from any trade.

### 20. Largest Losing Trade (`largest_losing_trade`)
**Formula:** Minimum (most negative) of all negative trade P&L values

The single largest loss from any trade. Stored as a negative value.

### 21. Max Consecutive Wins (`max_consecutive_wins`)
**Formula:** Longest streak of consecutive winning trades

Maximum number of profitable trades in a row.

### 22. Max Consecutive Losses (`max_consecutive_losses`)
**Formula:** Longest streak of consecutive losing trades

Maximum number of unprofitable trades in a row.

---

## Day Statistics

### 23. Total Calendar Days (`total_calendar_days`)
**Formula:** `(End Date - Start Date).days + 1` (inclusive)

Total number of calendar days from backtest start to end, inclusive.

### 24. Total Trading Days (`total_trading_days`)
**Formula:** Number of data points in equity curve

Number of days with actual trading data (may be less than calendar days due to weekends/holidays).

### 25. Days Profitable (`days_profitable`)
**Formula:** Count of days where equity increased

Number of days where the equity value was higher than the previous day.

### 26. Days Unprofitable (`days_unprofitable`)
**Formula:** Count of days where equity decreased

Number of days where the equity value was lower than the previous day.

### 27. Percent Days Profitable (`percent_days_profitable`)
**Formula:** `(Days Profitable / Total Trading Days) × 100`

Percentage of trading days that were profitable.

### 28. Percent Days Unprofitable (`percent_days_unprofitable`)
**Formula:** `(Days Unprofitable / Total Trading Days) × 100`

Percentage of trading days that were unprofitable.

---

## Drawdown Metrics

### 29. Maximum Drawdown Percentage (`max_drawdown_pct`)
**Formula:** `(Maximum Drawdown / Peak Value) × 100`

Maximum drawdown expressed as a percentage of the peak equity value.

### 30. Maximum Run-Up (`max_run_up`)
**Formula:** `Maximum Equity - Initial Capital`

The largest increase from initial capital (opposite of drawdown). Represents the peak profit before any decline.

### 31. Recovery Factor (`recovery_factor`)
**Formula:** `Net Profit / Maximum Drawdown`

Also known as NP/Max DD. Measures how much the strategy recovered relative to its worst drawdown.
- Higher is better
- If `max_drawdown == 0` and `net_profit > 0`: `recovery_factor = infinity`
- Otherwise: `recovery_factor = 0.0`

### 32. NP/Max DD (`np_max_dd`)
**Formula:** Same as `recovery_factor`

Alias for recovery factor.

---

## Advanced Metrics

### 33. R-Squared (`r_squared`)
**Formula:** Coefficient of determination from linear regression on equity curve

Calculated by:
1. Creating a linear regression model: `equity_value = a * day_number + b`
2. Calculating R² from the regression fit
3. Range: 0.0 to 1.0, where 1.0 = perfect linear fit

**Interpretation:** Measures how smoothly the equity curve grows. Higher values indicate more consistent, less volatile performance.

### 34. Sortino Ratio (`sortino_ratio`)
**Formula:** `(Mean Return - Risk-Free Rate) / Downside Deviation`

Similar to Sharpe ratio but only considers downside volatility:
1. Calculate period returns from equity curve
2. Calculate mean return
3. Calculate downside deviation (standard deviation of only negative returns)
4. Sortino = (mean - risk_free_rate) / downside_deviation

**Note:** If no downside returns exist, ratio is `infinity` if mean > risk_free_rate, else `0.0`.

### 35. Monte Carlo Score (`monte_carlo_score`)
**Formula:** Percentage of Monte Carlo simulations that exceeded the actual final equity value

Calculated by:
1. Performing 2500 random shuffles of the equity curve returns
2. Calculating final value for each shuffle
3. Counting how many shuffles exceeded the actual final value
4. Score = (count / 2500) × 100

**Interpretation:** Lower scores indicate more robust performance (fewer random permutations outperformed the actual result).

### 36. RINA Index (`rina_index`)
**Formula:** `Net Profit / (Average Drawdown × Percent Time In Market / 100)`

Measures risk-adjusted return considering both drawdown and time in market:
- If `avg_drawdown > 0` and `percent_time_in_market > 0`: 
  `rina_index = net_profit / (avg_drawdown * percent_time_in_market / 100.0)`
- Otherwise: `rina_index = 0.0`

**Interpretation:** Higher is better. Penalizes strategies that stay in the market too long or have high average drawdowns.

### 37. TradeStation Index (`tradestation_index`)
**Formula:** `(Net Profit × Days Profitable) / |Maximum Intraday Drawdown|`

Measures profit efficiency relative to intraday volatility:
- If `max_intraday_dd > 0`:
  `tradestation_index = (net_profit * days_profitable) / max_intraday_dd`
- Otherwise: `tradestation_index = infinity` if profit and win days > 0, else `0.0`

**Note:** Maximum intraday drawdown is the largest single-day drawdown (from open to close within a day).

### 38. NP × R² (`np_x_r2`)
**Formula:** `Net Profit × R-Squared`

Combined metric weighting profit by equity curve smoothness.

### 39. NP × PF (`np_x_pf`)
**Formula:** `Net Profit × Profit Factor`

Combined metric weighting profit by profit factor.

### 40. Annualized Net Profit (`annualized_net_profit`)
**Formula:** `Net Profit × (365 / Total Calendar Days)`

Only calculated if `total_calendar_days > 30`. Projects net profit to an annualized basis.

### 41. Annualized Return / Avg DD (`annualized_return_avg_dd`)
**Formula:** `Annualized Return / (Average Drawdown / Initial Capital × 100)`

Only calculated if `total_calendar_days > 30` and `avg_drawdown > 0`.
- `annualized_return = total_return_pct × (365 / total_calendar_days)`
- `annualized_return_avg_dd = annualized_return / (avg_drawdown / initial_capital × 100)`

### 42. Percent Time In Market (`percent_time_in_market`)
**Formula:** `(Total Time In Trades / Total Trading Days) × 100`

Calculated from trade list:
1. Sum all trade durations (entry to exit)
2. Divide by total trading days
3. Multiply by 100

**Note:** If trade data is unavailable, defaults to `0.0`.

---

## Walk-Forward Specific Metrics

### 43. Walk-Forward Efficiency (`walkforward_efficiency`)
**Formula:** `Out-of-Sample Return / In-Sample Return`

Only calculated for walk-forward optimization:
1. For each window, optimize parameters on in-sample (IS) data
2. Test best parameters on out-of-sample (OOS) data
3. Efficiency = OOS return / IS return

**Edge Cases:**
- If `IS return == 0` or `IS return < 0`: `efficiency = 0.0`
- Values > 1.0 indicate OOS outperformed IS (good sign)
- Values < 1.0 indicate OOS underperformed IS (common, expected)

**Interpretation:** Higher is better. Efficiency of 0.8 means OOS achieved 80% of IS performance.

---

## OOS Return Aggregation (Walk-Forward)

When multiple walk-forward windows exist, out-of-sample returns are **compounded** (not summed):

**Formula:** `Total OOS Return = (∏(1 + r_i) - 1) × 100`

Where `r_i` are the OOS return percentages for each window (converted to decimals).

**Example:**
- Window 1: +10% (r₁ = 0.10)
- Window 2: +5% (r₂ = 0.05)
- Window 3: -2% (r₃ = -0.02)
- **Compounded:** (1.10 × 1.05 × 0.98 - 1) × 100 = 13.19%

This correctly reflects the sequential nature of walk-forward testing where each window builds on the previous period.

**Note:** Net profit is **summed** (not compounded) because it's in dollars, not percentages.

---

## Data Sources

All metrics are calculated from:

1. **Equity Curve:** Mark-to-market account value over time
   - Extracted from strategy's `equity_curve` attribute (tracked by `EquityTrackingStrategy`)
   - Format: List of `{'date': datetime, 'value': float}` dictionaries

2. **Trade Analyzer:** Backtrader's TradeAnalyzer results
   - Provides trade statistics (win/loss counts, gross profit/loss)
   - Extracted via `cerebro.analyzers.trade.get_analysis()`

3. **Drawdown Analyzer:** Backtrader's DrawDown analyzer results
   - Provides maximum drawdown values
   - Extracted via `cerebro.analyzers.drawdown.get_analysis()`

4. **Sharpe Analyzer:** Backtrader's SharpeRatio analyzer results
   - Provides Sharpe ratio (if available)
   - Extracted via `cerebro.analyzers.sharpe.get_analysis()`

---

## Implementation Notes

### Trade Extraction

The system attempts to extract trade statistics from multiple sources:

1. **Strategy's `trades_log`:** If strategy maintains a manual trade log
2. **TradeAnalyzer:** Backtrader's built-in analyzer
3. **Fallback:** If extraction fails, all trade statistics default to `0.0` and a warning is logged

**Important:** Strategies should implement `trades_log` or ensure TradeAnalyzer provides complete data for accurate trade statistics.

### Edge Cases

- **Division by Zero:** Protected throughout (returns `0.0`, `infinity`, or `NaN` handling)
- **Empty Equity Curve:** Returns zero/default values for all metrics
- **No Trades:** Trade statistics default to zero
- **Missing Analyzers:** Falls back to manual calculations from equity curve
- **Short Periods:** Annualized metrics only calculated if `total_calendar_days > 30`

### Accuracy

- All calculations use floating-point arithmetic
- Comparison tolerances in tests use `places=2` (0.01 accuracy) for most metrics
- Some ratios (e.g., R², Sortino) may require higher precision (`places=4`)

---

## References

- MultiWalk Documentation: MultiWalk metric definitions
- Backtrader Analyzers: https://www.backtrader.com/docu/analyzers/
- Standard Financial Metrics: Sharpe Ratio, Sortino Ratio, R-Squared definitions

---

**Last Updated:** Implementation Date
**Version:** 1.0

