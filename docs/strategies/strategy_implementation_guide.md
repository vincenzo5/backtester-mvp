# Strategy Implementation Guide

## Purpose

This guide provides step-by-step instructions for implementing new trading strategies in the backtester system. Follow this guide precisely when creating new strategies to ensure compatibility with the backtest engine.

## Strategy Interface Overview

All strategies inherit from `BaseStrategy` (defined in `src/backtester/strategies/base_strategy.py`). The interface requires:

1. **Required Class Method:**
   - `get_required_indicators(cls, params: Dict[str, Any]) -> List[IndicatorSpec]`
     - Declares which indicators should be pre-computed before backtest
     - Returns list of IndicatorSpec objects
   
2. **Required Instance Methods:**
   - `next(self)` - Execute trading logic on each bar
   - `__init__(self)` - Initialize strategy state

3. **Optional Class Method:**
   - `get_required_data_sources(cls) -> List[DataSourceProvider]`
     - Declares third-party data sources to fetch and align

4. **Optional Instance Methods:**
   - `notify_order(self, order)` - Handle order execution notifications
   - `stop(self)` - Called at end of backtesting for cleanup/logging

## Step-by-Step Implementation

### Step 1: Create the Strategy Class File

**Location:** `src/backtester/strategies/[strategy_name].py`

**Template:**

```python
"""
[Brief description of what this strategy does].

[More detailed explanation if needed].
"""

import backtrader as bt
from backtester.strategies.base_strategy import BaseStrategy
from backtester.indicators.base import IndicatorSpec
from typing import List, Dict, Any


class YourStrategyName(BaseStrategy):
    """
    [Detailed description of the strategy].
    
    Trading Logic:
        - Buy Signal: [Description of conditions for entering a position]
        - Sell Signal: [Description of conditions for exiting a position]
    
    Parameters:
        - param1: [Description of parameter] (default: 20)
        - param2: [Description of parameter] (default: 50)
        - printlog: Enable/disable logging (default: True)
    
    [Additional notes about methodology or performance considerations].
    """
    
    params = (
        ('param1', 20),     # [Description]
        ('param2', 50),     # [Description]
        ('printlog', True),  # Enable/disable logging
    )
    
    @classmethod
    def get_required_indicators(cls, params: Dict[str, Any]) -> List[IndicatorSpec]:
        """
        Declare required indicators for this strategy.
        
        These indicators will be pre-computed before the backtest runs,
        making it efficient for walk-forward optimization.
        
        Args:
            params: Strategy parameters from config (e.g., {'param1': 20})
        
        Returns:
            List of IndicatorSpec objects
        
        Notes:
            - Use params.get() to access parameters with defaults
            - Column names should be descriptive and unique
            - Indicators are accessible via self.data.[column_name][0] in next()
        """
        return [
            IndicatorSpec(
                'INDICATOR_TYPE',
                {'indicator_param': params.get('param1', 20)},
                'COLUMN_NAME'
            ),
            # Add more indicators as needed
        ]
    
    def __init__(self):
        """Initialize strategy state."""
        super().__init__()
        
        # Initialize tracking variables
        self.order = None  # Track pending orders
        self.buy_count = 0  # Count buy signals (optional)
        self.sell_count = 0  # Count sell signals (optional)
        
        # CRITICAL: If you need backtrader's built-in indicators,
        # calculate them here (not recommended - use get_required_indicators instead)
        # self.custom_sma = bt.indicators.SMA(self.data.close, period=20)
    
    def next(self):
        """
        Execute trading logic on each bar.
        
        Access pre-computed indicators via self.data:
        - self.data.COLUMN_NAME[0] - Current indicator value
        - self.data.close[0] - Current close price
        - self.data.high[0] - Current high price
        - self.data.low[0] - Current low price
        - self.data.volume[0] - Current volume
        
        Backtrader indexing:
        - [0] = current bar
        - [-1] = previous bar
        - [-2] = two bars ago
        
        Notes:
            - Check if enough data available before using indicators
            - Check for pending orders before submitting new ones
            - Handle NaN values appropriately
        """
        # Skip if we don't have enough data
        if len(self.data) < self.params.param1:  # Adjust based on your needs
            return
        
        # Skip if we have a pending order
        if self.order:
            return
        
        # Access pre-computed indicators
        indicator_value = self.data.COLUMN_NAME[0]
        current_price = self.data.close[0]
        
        # Check for NaN values
        if bt.indicators.isnan(indicator_value):
            return
        
        # YOUR TRADING LOGIC HERE
        # Example pattern:
        
        # Buy signal: Enter position
        if not self.position:
            if self.YOUR_BUY_CONDITION:
                # Calculate position size (crypto supports fractional positions)
                cash = self.broker.getcash()
                size = (cash * 0.9) / current_price  # Use 90% of cash
                
                # Minimum size threshold to avoid dust trades
                min_size = 0.0001
                if size >= min_size:
                    self.buy_count += 1
                    self.log(f'ORDER: BUY @ ${current_price:.2f}')
                    self.order = self.buy(size=size)
                else:
                    self.log(f'INSUFFICIENT CASH (need {min_size}, have {size})')
        
        # Sell signal: Exit position
        else:
            if self.YOUR_SELL_CONDITION:
                self.sell_count += 1
                position_size = self.position.size
                self.log(f'ORDER: SELL({position_size}) @ ${current_price:.2f}')
                self.order = self.sell()
    
    def notify_order(self, order):
        """
        Handle order notifications.
        
        Called by backtrader when order status changes.
        
        Args:
            order: Backtrader order object
        
        Notes:
            - Always call super().notify_order() for proper trade tracking
            - Order status: Submitted, Accepted, Completed, Canceled, Margin, Rejected
        """
        # CRITICAL: Call parent first to populate trades_log
        super().notify_order(order)
        
        # Add custom logging if needed
        if order.status in [order.Completed]:
            price = order.executed.price
            size = order.executed.size
            
            if order.isbuy() and self.params.printlog:
                self.log(f'BUY EXECUTED: {size} @ ${price:.2f}')
            elif order.issell() and self.params.printlog:
                self.log(f'SELL EXECUTED: {abs(size)} @ ${price:.2f}')
    
    def stop(self):
        """
        Called at the end of backtesting.
        
        Use for final logging, cleanup, or performance summary.
        """
        if self.params.printlog:
            self.log(f'Strategy Final Value: ${self.broker.getvalue():.2f}')
            if self.buy_count > 0:
                self.log(f'Total Buy Signals: {self.buy_count}')
            if self.sell_count > 0:
                self.log(f'Total Sell Signals: {self.sell_count}')
```

### Step 2: Register the Strategy

**Location:** Update `src/backtester/strategies/__init__.py`

```python
"""
Strategy module for dynamic strategy loading.

This module provides a registry of trading strategies that can be dynamically
loaded based on configuration.
"""

from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.strategies.rsi_sma_strategy import RSISMAStrategy
from backtester.strategies.your_strategy_name import YourStrategyName  # ADD THIS LINE


# Strategy registry mapping names to classes
STRATEGY_REGISTRY = {
    'sma_cross': SMACrossStrategy,
    'rsi_sma': RSISMAStrategy,
    'your_strategy_name': YourStrategyName,  # ADD THIS LINE
}


def get_strategy_class(strategy_name):
    """
    Get a strategy class by name.
    
    Args:
        strategy_name (str): Name of the strategy (e.g., 'sma_cross')
    
    Returns:
        class: Strategy class that can be instantiated by backtrader
    
    Raises:
        ValueError: If strategy_name is not found in registry
    """
    if strategy_name not in STRATEGY_REGISTRY:
        available = ', '.join(STRATEGY_REGISTRY.keys())
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Available strategies: {available}"
        )
    
    return STRATEGY_REGISTRY[strategy_name]


__all__ = ['get_strategy_class', 'SMACrossStrategy', 'RSISMAStrategy', 'YourStrategyName']
```

### Step 3: Reference Implementation Examples

Study these existing implementations for patterns:

**SMA Crossover Strategy:**
- File: `src/backtester/strategies/sma_cross.py`
- Pattern: Trend-following strategy using moving average crossover
- Indicators: SMA (fast and slow periods)

**RSI + SMA Strategy:**
- File: `src/backtester/strategies/rsi_sma_strategy.py`
- Pattern: Mean reversion strategy using RSI oversold/overbought levels
- Indicators: RSI, SMA

### Step 4: Key Implementation Requirements

**CRITICAL Requirements:**

1. **Indicator Declaration:** Use `get_required_indicators()` to declare indicators
   ```python
   @classmethod
   def get_required_indicators(cls, params):
       return [
           IndicatorSpec('SMA', {'timeperiod': params['fast']}, 'SMA_fast'),
           IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
       ]
   ```

2. **Indicator Access:** Use `self.data.[COLUMN_NAME][0]` in next()
   ```python
   # CORRECT
   sma = self.data.SMA_fast[0]
   
   # WRONG - don't calculate indicators in __init__ if declared in get_required_indicators
   self.sma = bt.indicators.SMA(self.data.close, period=20)
   ```

3. **Pending Order Check:** Check for pending orders before submitting new ones
   ```python
   if self.order:
       return  # Don't submit new orders
   ```

4. **Empty Data Check:** Check data available before using indicators
   ```python
   if len(self.data) < self.params.period:
       return  # Not enough data yet
   ```

5. **NaN Handling:** Check for NaN values before using indicators
   ```python
   if bt.indicators.isnan(indicator_value):
       return
   ```

6. **Parent Call:** Always call super() in notify_order()
   ```python
   def notify_order(self, order):
       super().notify_order(order)  # CRITICAL for trade tracking
       # Your custom logic here
   ```

7. **Name Uniqueness:** Strategy name must be unique in registry
   - Use snake_case: `'your_strategy_name'`
   - Be descriptive

## Testing Your Strategy

### Smoke Test

Create `tests/smoke/test_[strategy_name]_init.py`:

```python
"""Smoke tests for [StrategyName] initialization."""

import unittest
import pytest
from backtester.strategies import get_strategy_class
from backtester.indicators.base import IndicatorSpec

@pytest.mark.smoke
class Test[StrategyName]Initialization(unittest.TestCase):
    """Test [StrategyName] can be instantiated."""
    
    def test_strategy_can_be_imported(self):
        """Strategy class can be imported."""
        from backtester.strategies.your_strategy_name import YourStrategyName
        self.assertIsNotNone(YourStrategyName)
    
    def test_strategy_can_be_instantiated(self):
        """Strategy can be instantiated without errors."""
        strategy_class = get_strategy_class('your_strategy_name')
        self.assertIsNotNone(strategy_class)
        instance = strategy_class()
        self.assertIsNotNone(instance)
    
    def test_strategy_has_required_methods(self):
        """Strategy has all required methods."""
        strategy_class = get_strategy_class('your_strategy_name')
        self.assertTrue(hasattr(strategy_class, 'get_required_indicators'))
        self.assertTrue(hasattr(strategy_class, 'next'))
    
    def test_get_required_indicators_returns_list(self):
        """get_required_indicators returns a list."""
        strategy_class = get_strategy_class('your_strategy_name')
        params = {'param1': 20, 'param2': 50}
        indicators = strategy_class.get_required_indicators(params)
        self.assertIsInstance(indicators, list)
    
    def test_get_required_indicators_returns_specs(self):
        """get_required_indicators returns IndicatorSpec objects."""
        strategy_class = get_strategy_class('your_strategy_name')
        params = {'param1': 20, 'param2': 50}
        indicators = strategy_class.get_required_indicators(params)
        if indicators:  # Not all strategies require indicators
            for indicator in indicators:
                self.assertIsInstance(indicator, IndicatorSpec)
```

### Unit Test

Create `tests/unit/test_[strategy_name].py`:

```python
"""Unit tests for [StrategyName]."""

import unittest
import pytest
from backtester.strategies import get_strategy_class
from backtester.indicators.base import IndicatorSpec

@pytest.mark.unit
class Test[StrategyName](unittest.TestCase):
    """Test [StrategyName] functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.strategy_class = get_strategy_class('your_strategy_name')
        self.params = {'param1': 20, 'param2': 50}
    
    def test_get_required_indicators_uses_params(self):
        """get_required_indicators uses provided parameters."""
        # Test with different parameters
        params1 = {'param1': 10, 'param2': 20}
        params2 = {'param1': 30, 'param2': 60}
        
        indicators1 = self.strategy_class.get_required_indicators(params1)
        indicators2 = self.strategy_class.get_required_indicators(params2)
        
        # Should return different indicators based on params (or same if not parameterized)
        # Adjust based on your strategy's behavior
        pass
    
    def test_strategy_has_default_params(self):
        """Strategy has correct default parameters."""
        instance = self.strategy_class()
        
        # Check that params are accessible
        self.assertIsNotNone(instance.params.param1)
        self.assertIsNotNone(instance.params.param2)
        self.assertIsNotNone(instance.params.printlog)
    
    def test_strategy_initializes_state(self):
        """Strategy initializes tracking state."""
        instance = self.strategy_class()
        
        self.assertIsNone(instance.order)
        # Add checks for other tracking variables if defined
```

## Usage

Once implemented and registered, your strategy can be used in backtests:

**Configuration (`config/strategy.yaml`):**

```yaml
strategy:
  name: your_strategy_name
```

**Note:** Currently, strategy parameters are defined in the `params` tuple within the strategy code. To make them configurable via YAML configuration, you would need to add support in `config/strategy.yaml` and the configuration system (see Configuration Standards in the rules).

## Common Patterns

### Pattern 1: Trend Following with Moving Averages

```python
@classmethod
def get_required_indicators(cls, params):
    return [
        IndicatorSpec('SMA', {'timeperiod': params['fast']}, 'SMA_fast'),
        IndicatorSpec('SMA', {'timeperiod': params['slow']}, 'SMA_slow'),
    ]

def next(self):
    sma_fast = self.data.SMA_fast[0]
    sma_slow = self.data.SMA_slow[0]
    
    # Buy when fast crosses above slow
    if not self.position and sma_fast > sma_slow:
        self.buy()
    
    # Sell when fast crosses below slow
    elif self.position and sma_fast < sma_slow:
        self.sell()
```

### Pattern 2: Mean Reversion with RSI

```python
@classmethod
def get_required_indicators(cls, params):
    return [
        IndicatorSpec('RSI', {'timeperiod': params['rsi_period']}, 'RSI'),
    ]

def next(self):
    rsi = self.data.RSI[0]
    
    # Buy when oversold (mean reversion)
    if not self.position and rsi < params['rsi_oversold']:
        self.buy()
    
    # Sell when overbought (mean reversion)
    elif self.position and rsi > params['rsi_overbought']:
        self.sell()
```

### Pattern 3: Multi-Indicator Confirmation

```python
@classmethod
def get_required_indicators(cls, params):
    return [
        IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
        IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
        IndicatorSpec('MACD', {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9}, 'MACD'),
    ]

def next(self):
    sma = self.data.SMA_20[0]
    rsi = self.data.RSI_14[0]
    macd_line = self.data.MACD_macd[0]
    signal_line = self.data.MACD_signal[0]
    
    # Buy when all indicators agree
    is_uptrend = self.data.close[0] > sma
    is_not_overbought = rsi < 70
    macd_bullish = macd_line > signal_line
    
    if not self.position and is_uptrend and is_not_overbought and macd_bullish:
        self.buy()
    
    # Sell when any indicator flips
    elif self.position and (self.data.close[0] < sma or rsi > 70 or macd_line < signal_line):
        self.sell()
```

### Pattern 4: Using Custom Indicators

```python
from backtester.indicators.base import register_custom_indicator
import pandas as pd

# Register custom indicator first (can be in same file or imported)
def custom_atr_mean(df, params):
    """Mean of ATR over last N periods"""
    from ta.volatility import AverageTrueRange
    atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=params['atr_period'])
    return atr.average_true_range().rolling(window=params['mean_period']).mean()

register_custom_indicator('ATR_MEAN', custom_atr_mean)

class YourStrategyName(BaseStrategy):
    @classmethod
    def get_required_indicators(cls, params):
        return [
            IndicatorSpec('ATR_MEAN', {'atr_period': 14, 'mean_period': 20}, 'ATR_MEAN'),
        ]
    
    def next(self):
        atr_mean = self.data.ATR_MEAN[0]
        # Use in your trading logic
```

## Available Indicators

Common indicators available through the indicator library (see `src/backtester/indicators/library.py`):

- **Moving Averages:** SMA, EMA
- **Momentum:** RSI, Stochastic
- **Trend:** MACD
- **Volatility:** Bollinger Bands, ATR
- **Volume:** Volume SMA, On Balance Volume

You can also register custom indicators using `register_custom_indicator()` from `backtester.indicators.base`.

## Checklist

Before submitting your strategy implementation:

- [ ] Strategy class inherits from `BaseStrategy`
- [ ] `get_required_indicators()` method implemented
- [ ] `next()` method implemented
- [ ] `__init__()` calls `super().__init__()`
- [ ] Strategy registered in `strategies/__init__.py`
- [ ] Strategy name is unique and uses snake_case
- [ ] Pending orders checked before submitting new orders
- [ ] Check for enough data before using indicators
- [ ] Check for NaN values before using indicators
- [ ] `notify_order()` calls `super().notify_order()`
- [ ] Smoke tests created
- [ ] Unit tests created
- [ ] Docstrings added to class and methods
- [ ] Code follows existing patterns
- [ ] Parameters use `params.get()` with defaults

## Files to Create/Modify

1. **Create:** `src/backtester/strategies/[strategy_name].py`
2. **Modify:** `src/backtester/strategies/__init__.py`
3. **Create:** `tests/smoke/test_[strategy_name]_init.py`
4. **Create:** `tests/unit/test_[strategy_name].py`

## Reference Files

- Base Interface: `src/backtester/strategies/base_strategy.py`
- Registry: `src/backtester/strategies/__init__.py`
- Example: `src/backtester/strategies/sma_cross.py`
- Example: `src/backtester/strategies/rsi_sma_strategy.py`
- Indicator System: `src/backtester/indicators/base.py`
- Indicator Library: `src/backtester/indicators/library.py`
- Engine: `src/backtester/backtest/engine.py` (how strategies are used)

---

## Quick Start Template

Copy this template to start implementing a new strategy:

```python
"""
[Description] strategy.

[Detailed explanation].
"""

import backtrader as bt
from backtester.strategies.base_strategy import BaseStrategy
from backtester.indicators.base import IndicatorSpec
from typing import List, Dict, Any


class YourStrategyName(BaseStrategy):
    """[Description]."""
    
    params = (
        ('param1', 20),
        ('printlog', True),
    )
    
    @classmethod
    def get_required_indicators(cls, params: Dict[str, Any]) -> List[IndicatorSpec]:
        """Declare required indicators."""
        return [
            IndicatorSpec('SMA', {'timeperiod': params.get('param1', 20)}, 'SMA_20'),
        ]
    
    def __init__(self):
        """Initialize strategy."""
        super().__init__()
        self.order = None
    
    def next(self):
        """Execute trading logic on each bar."""
        # Skip if not enough data
        if len(self.data) < self.params.param1:
            return
        
        # Skip if pending order
        if self.order:
            return
        
        # Access indicators
        sma = self.data.SMA_20[0]
        
        # Check for NaN
        if bt.indicators.isnan(sma):
            return
        
        # TODO: Implement your trading logic here
        pass
    
    def notify_order(self, order):
        """Handle order notifications."""
        super().notify_order(order)  # CRITICAL
    
    def stop(self):
        """Called at end of backtest."""
        if self.params.printlog:
            self.log(f'Final Value: ${self.broker.getvalue():.2f}')
```

---

This guide provides everything needed to implement new strategies. Follow the steps, templates, examples, and checklist for successful implementation.

