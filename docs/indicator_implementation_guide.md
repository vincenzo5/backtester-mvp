# Indicator Implementation Guide

## Purpose

This guide provides step-by-step instructions for implementing new indicators in the backtester system. Follow this guide precisely when creating new indicators to ensure compatibility with the indicator system.

## Indicator Interface Overview

All custom indicators are functions that follow a standard interface:

1. **Function Signature:**
   - `compute_func(df: pd.DataFrame, params: Dict[str, Any]) -> Union[pd.Series, pd.DataFrame]`
   - Must accept OHLCV DataFrame and parameter dictionary
   - Must return pandas Series (single-value indicator) or DataFrame (multi-value indicator)

2. **Registration:**
   - Use `register_custom_indicator(name, compute_func)` to register
   - Indicator name must be unique (not conflict with built-in TA-Lib indicators)
   - Registration happens at module import time

3. **Usage:**
   - Use `IndicatorSpec(indicator_type=name, params={...}, column_name='...')` to reference
   - Indicators are pre-computed before backtests for optimal performance

## Step-by-Step Implementation

### Step 1: Create the Indicator Function File

**Location:** `src/backtester/indicators/implementations/[category]/[indicator_name].py`

**Category Options:**
- `trend/` - Trend-based indicators (e.g., moving averages, ADX)
- `momentum/` - Momentum indicators (e.g., RSI, Stochastic)
- `volatility/` - Volatility indicators (e.g., ATR, Bollinger Bands)
- `volume/` - Volume-based indicators
- `custom/` - Specialized or composite indicators
- Create a new subdirectory if needed

**Template for Single-Value Indicator:**

```python
"""
[Brief description of what this indicator computes].

[More detailed explanation if needed].

Returns a single Series value per bar (e.g., RSI, SMA).
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


def [indicator_name](df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """
    Compute [indicator description] for each bar.
    
    Args:
        df: OHLCV DataFrame with datetime index
            Must have columns: ['open', 'high', 'low', 'close', 'volume']
        params: Parameter dictionary with indicator configuration
            Required keys:
            - 'param1': [Description] (default: [value])
            - 'param2': [Description] (default: [value])
    
    Returns:
        Series with indicator values indexed by df.index
        - Index must match df.index exactly
        - NaN values allowed for initial periods (e.g., rolling window warm-up)
    
    Notes:
        - Handle empty DataFrame gracefully
        - Handle NaN values appropriately (rolling windows may produce NaN)
        - Ensure index alignment with input DataFrame
        - Use consistent parameter names and types
    
    Example:
        >>> df = pd.DataFrame({
        ...     'close': [100, 101, 102, 103, 104],
        ...     'volume': [1000, 1100, 1200, 1300, 1400]
        ... })
        >>> result = [indicator_name](df, {'period': 3})
        >>> print(result.iloc[-1])  # Latest value
    """
    # CRITICAL: Handle empty DataFrame
    if df.empty:
        return pd.Series(dtype=float, index=df.index)
    
    # Extract parameters with defaults
    param1 = params.get('param1', [default_value])
    param2 = params.get('param2', [default_value])
    
    # YOUR INDICATOR COMPUTATION LOGIC HERE
    # Example patterns:
    # 
    # Pattern 1: Rolling window calculation
    #    result = df['close'].rolling(window=param1).mean()
    # 
    # Pattern 2: Using existing indicators
    #    from ta.trend import SMAIndicator
    #    sma = SMAIndicator(close=df['close'], window=param1)
    #    result = sma.sma_indicator()
    # 
    # Pattern 3: Complex multi-step calculation
    #    step1 = df['high'] - df['low']
    #    step2 = step1.rolling(window=param1).mean()
    #    result = step2 * param2
    
    # TEMPLATE CODE - Replace with your logic:
    result = pd.Series(index=df.index, dtype=float)
    
    # Your computation here
    # ...
    
    # CRITICAL: Ensure index matches input DataFrame
    if not result.index.equals(df.index):
        result = result.reindex(df.index)
    
    # CRITICAL: Return Series with correct index
    return result
```

**Template for Multi-Value Indicator:**

```python
"""
[Brief description] indicator.

Returns multiple columns (e.g., MACD returns macd, signal, hist).
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


def [indicator_name](df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """
    Compute [indicator description] for each bar.
    
    Returns DataFrame with multiple columns (e.g., ['upper', 'middle', 'lower']).
    
    Args:
        df: OHLCV DataFrame with datetime index
        params: Parameter dictionary
    
    Returns:
        DataFrame with indicator values indexed by df.index
        - Index must match df.index exactly
        - Column names will be prefixed with column_name from IndicatorSpec
        - Example: IndicatorSpec(..., column_name='BB') → columns: BB_upper, BB_middle, BB_lower
    
    Example:
        >>> result = [indicator_name](df, {'period': 20})
        >>> # Returns DataFrame with columns: ['value1', 'value2', 'value3']
    """
    if df.empty:
        return pd.DataFrame(index=df.index)
    
    # Extract parameters
    param1 = params.get('param1', [default_value])
    
    # YOUR COMPUTATION LOGIC HERE
    # Compute multiple values
    value1 = ...  # Series
    value2 = ...  # Series
    value3 = ...  # Series
    
    # CRITICAL: Return DataFrame with named columns
    result = pd.DataFrame({
        'value1': value1,
        'value2': value2,
        'value3': value3,
    }, index=df.index)
    
    return result
```

### Step 2: Register the Indicator

**Location:** Create or update `src/backtester/indicators/implementations/[category]/__init__.py`

**If category already exists:**

```python
"""
[Category description] indicators.

Auto-registers all [category]-based indicators.
"""

from backtester.indicators.base import register_custom_indicator
from backtester.indicators.implementations.[category].[indicator_name] import [indicator_name]

# Auto-register indicators
register_custom_indicator('[INDICATOR_NAME]', [indicator_name])
```

**If creating a new category:**

1. Create `src/backtester/indicators/implementations/[category]/__init__.py`:

```python
"""
[Category description] indicators.

Auto-registers all [category]-based indicators.
"""

from backtester.indicators.base import register_custom_indicator
from backtester.indicators.implementations.[category].[indicator_name] import [indicator_name]

# Auto-register indicators
register_custom_indicator('[INDICATOR_NAME]', [indicator_name])
```

2. Update `src/backtester/indicators/implementations/__init__.py` to import the new category:

```python
"""
Indicator implementations package.

This module automatically registers all indicator implementations on import.
Import this module to trigger auto-registration of all indicators.
"""

# Import all indicator implementation packages to trigger registration
from backtester.indicators.implementations import trend  # noqa
from backtester.indicators.implementations import [category]  # ADD THIS LINE
```

### Step 3: Reference Implementation Examples

Study these existing implementations for patterns:

**Built-in TA-Lib Indicators:**
- File: `src/backtester/indicators/library.py`
- Pattern: Wrap TA-Lib classes, handle parameters, return Series/DataFrame
- Examples: SMA, EMA, RSI, MACD, BBANDS

**Single-Value Pattern:**
```python
def simple_volume_ma(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """Simple moving average of volume."""
    period = params.get('period', 20)
    return df['volume'].rolling(window=period).mean()
```

**Multi-Value Pattern:**
```python
def bollinger_bands_custom(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Custom Bollinger Bands computation."""
    period = params.get('period', 20)
    std_dev = params.get('std_dev', 2)
    
    middle = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    return pd.DataFrame({
        'upper': middle + (std * std_dev),
        'middle': middle,
        'lower': middle - (std * std_dev),
    }, index=df.index)
```

### Step 4: Key Implementation Requirements

**CRITICAL Requirements:**

1. **Index Matching:** Returned Series/DataFrame index MUST match `df.index` exactly
   ```python
   # CORRECT
   result = pd.Series(values, index=df.index)
   return result
   
   # WRONG
   result = pd.Series(values)  # Missing index
   return result
   ```

2. **Empty DataFrame:** Always handle empty input
   ```python
   if df.empty:
       return pd.Series(dtype=float, index=df.index)  # Single value
       # OR
       return pd.DataFrame(index=df.index)  # Multi value
   ```

3. **NaN Handling:** Allow NaN for initial periods (rolling windows)
   ```python
   # Rolling indicators naturally produce NaN for first N periods
   result = df['close'].rolling(window=period).mean()
   # This is expected and correct - no need to fill NaN
   ```

4. **Parameter Defaults:** Always provide sensible defaults
   ```python
   period = params.get('period', 14)  # Provide default
   ```

5. **Name Uniqueness:** Indicator name MUST be unique and not conflict with built-ins
   - Use UPPER_SNAKE_CASE: `'CUSTOM_RSI'`, `'VOLUME_PROFILE'`
   - Built-in names: `'SMA'`, `'EMA'`, `'RSI'`, `'MACD'`, `'BBANDS'`
   - Check `IndicatorLibrary._get_ta_indicator_names()` for built-ins

6. **Return Type:**
   - Single value per bar → return `pd.Series`
   - Multiple values per bar → return `pd.DataFrame` with named columns
   - Multi-value columns are automatically prefixed: `IndicatorSpec(..., column_name='BB')` → `BB_upper`, `BB_lower`

## Testing Your Indicator

### Smoke Test

Create `tests/smoke/test_[indicator_name]_init.py`:

```python
"""Smoke tests for [IndicatorName] initialization."""

import unittest
import pytest
from backtester.indicators.base import get_custom_indicator

@pytest.mark.smoke
class Test[IndicatorName]Initialization(unittest.TestCase):
    """Test [IndicatorName] can be imported and registered."""
    
    def test_indicator_can_be_imported(self):
        """Indicator function can be imported."""
        from backtester.indicators.implementations.[category].[indicator_name] import [indicator_name]
        self.assertIsNotNone([indicator_name])
        self.assertTrue(callable([indicator_name]))
    
    def test_indicator_is_registered(self):
        """Indicator is registered in the registry."""
        indicator = get_custom_indicator('[INDICATOR_NAME]')
        self.assertIsNotNone(indicator)
        self.assertEqual(indicator.name, '[INDICATOR_NAME]')
    
    def test_indicator_has_compute_function(self):
        """Indicator has a compute function."""
        indicator = get_custom_indicator('[INDICATOR_NAME]')
        self.assertTrue(hasattr(indicator, 'compute_func'))
        self.assertTrue(callable(indicator.compute_func))
```

### Unit Test

Create `tests/unit/test_[indicator_name].py`:

```python
"""Unit tests for [IndicatorName] indicator."""

import unittest
import pytest
import pandas as pd
import numpy as np
from backtester.indicators.base import get_custom_indicator, IndicatorSpec
from backtester.indicators.library import IndicatorLibrary
from tests.conftest import sample_ohlcv_data

@pytest.mark.unit
class Test[IndicatorName](unittest.TestCase):
    """Test [IndicatorName] computation logic."""
    
    def setUp(self):
        """Set up test environment."""
        self.df = sample_ohlcv_data(num_candles=100)
        self.library = IndicatorLibrary()
        self.indicator = get_custom_indicator('[INDICATOR_NAME]')
    
    def test_compute_returns_series(self):
        """compute() returns pandas Series for single-value indicator."""
        result = self.indicator.compute(self.df, {'param1': 20})
        self.assertIsInstance(result, pd.Series)
    
    def test_compute_index_matches_dataframe(self):
        """Computed Series index matches DataFrame index."""
        result = self.indicator.compute(self.df, {'param1': 20})
        pd.testing.assert_index_equal(result.index, self.df.index)
    
    def test_compute_with_default_params(self):
        """Indicator works with default parameters."""
        # Assuming default param1 value
        result = self.indicator.compute(self.df, {})
        self.assertEqual(len(result), len(self.df))
    
    def test_compute_with_custom_params(self):
        """Indicator accepts custom parameters."""
        result = self.indicator.compute(self.df, {'param1': 30, 'param2': 0.8})
        self.assertEqual(len(result), len(self.df))
    
    def test_empty_dataframe_handling(self):
        """Empty DataFrame returns empty Series with correct index."""
        empty_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        empty_df.index = pd.DatetimeIndex([])
        result = self.indicator.compute(empty_df, {'param1': 20})
        self.assertEqual(len(result), 0)
        pd.testing.assert_index_equal(result.index, empty_df.index)
    
    def test_works_with_indicator_library(self):
        """Indicator works through IndicatorLibrary."""
        spec = IndicatorSpec('[INDICATOR_NAME]', {'param1': 20}, 'test_indicator')
        result_df = self.library.compute_all(self.df, [spec])
        
        self.assertIn('test_indicator', result_df.columns)
        self.assertEqual(len(result_df), len(self.df))
    
    def test_output_values_are_reasonable(self):
        """Output values are within expected range."""
        result = self.indicator.compute(self.df, {'param1': 20})
        valid_values = result.dropna()
        
        if len(valid_values) > 0:
            # Add assertions based on your indicator's expected range
            # Example: RSI should be between 0 and 100
            # self.assertTrue(all(0 <= v <= 100 for v in valid_values))
            pass
```

## Usage

Once implemented and registered, your indicator can be used in strategies:

**In Strategy (`get_required_indicators`):**

```python
from backtester.indicators.base import IndicatorSpec

class MyStrategy(BaseStrategy):
    @classmethod
    def get_required_indicators(cls, params):
        return [
            IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
            IndicatorSpec('[INDICATOR_NAME]', {'param1': 20}, 'my_indicator'),  # Your new indicator
        ]
    
    def next(self):
        sma = self.data.SMA_20[0]
        my_value = self.data.my_indicator[0]  # Access your indicator
        # Your trading logic here
```

**Direct Computation:**

```python
from backtester.indicators.library import IndicatorLibrary
from backtester.indicators.base import IndicatorSpec

lib = IndicatorLibrary()
df = load_ohlcv_data()

spec = IndicatorSpec('[INDICATOR_NAME]', {'param1': 20}, 'my_indicator')
enriched_df = lib.compute_all(df, [spec])

# enriched_df now has column 'my_indicator'
```

## Common Patterns

### Pattern 1: Simple Rolling Window

```python
def rolling_mean(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """Simple moving average."""
    period = params.get('period', 20)
    return df['close'].rolling(window=period).mean()
```

### Pattern 2: Percentage-Based Indicator

```python
def percent_change(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """Percentage change over N periods."""
    period = params.get('period', 1)
    return df['close'].pct_change(periods=period) * 100
```

### Pattern 3: Composite Indicator (Using Other Indicators)

```python
def custom_momentum(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """Custom momentum indicator combining RSI and price change."""
    from ta.momentum import RSIIndicator
    
    rsi_period = params.get('rsi_period', 14)
    change_period = params.get('change_period', 10)
    
    rsi = RSIIndicator(close=df['close'], window=rsi_period).rsi()
    price_change = df['close'].pct_change(periods=change_period)
    
    # Combine indicators
    momentum = (rsi / 100) * price_change
    return momentum
```

### Pattern 4: Multi-Column Indicator

```python
def custom_bands(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Custom bands indicator returning upper, middle, lower."""
    period = params.get('period', 20)
    multiplier = params.get('multiplier', 2.0)
    
    middle = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    return pd.DataFrame({
        'upper': middle + (std * multiplier),
        'middle': middle,
        'lower': middle - (std * multiplier),
    }, index=df.index)
```

### Pattern 5: Volume-Based Indicator

```python
def volume_ratio(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """Current volume vs. average volume ratio."""
    period = params.get('period', 20)
    avg_volume = df['volume'].rolling(window=period).mean()
    return df['volume'] / avg_volume
```

## Adding Built-in TA-Lib Indicators

To add support for a new indicator from the 'ta' library:

**Location:** Update `src/backtester/indicators/library.py`

**Steps:**

1. Add indicator name to `_get_ta_indicator_names()`:
```python
def _get_ta_indicator_names(self) -> List[str]:
    return ['SMA', 'EMA', 'RSI', 'MACD', 'BBANDS', 'NEW_INDICATOR']  # ADD HERE
```

2. Add computation case in `_compute_ta_indicator()`:
```python
elif indicator_type == 'NEW_INDICATOR':
    from ta.category import NewIndicatorClass
    indicator = NewIndicatorClass(
        close=df['close'],
        window=params.get('timeperiod', 14)
    )
    return indicator.new_indicator()  # Return Series or DataFrame
```

## Checklist

Before submitting your indicator implementation:

- [ ] Indicator function follows signature: `(df, params) -> Series/DataFrame`
- [ ] Function registered in appropriate `__init__.py`
- [ ] Category `__init__.py` imports and registers indicator
- [ ] Main `implementations/__init__.py` imports category (if new category)
- [ ] Indicator name is unique and uses UPPER_SNAKE_CASE
- [ ] Indicator name does not conflict with built-in TA-Lib indicators
- [ ] Returned Series/DataFrame index matches `df.index` exactly
- [ ] Empty DataFrame handled gracefully
- [ ] Parameters have sensible defaults
- [ ] NaN values handled appropriately (allowed for warm-up periods)
- [ ] Smoke tests created
- [ ] Unit tests created
- [ ] Docstrings added to function
- [ ] Code follows existing patterns
- [ ] Works through `IndicatorLibrary.compute_all()`

## Files to Create/Modify

1. **Create:** `src/backtester/indicators/implementations/[category]/[indicator_name].py`
2. **Modify:** `src/backtester/indicators/implementations/[category]/__init__.py`
3. **Modify:** `src/backtester/indicators/implementations/__init__.py` (if new category)
4. **Create:** `tests/smoke/test_[indicator_name]_init.py`
5. **Create:** `tests/unit/test_[indicator_name].py`

## Reference Files

- Base Interface: `src/backtester/indicators/base.py`
- Registry Functions: `register_custom_indicator()`, `get_custom_indicator()` in `base.py`
- Library: `src/backtester/indicators/library.py` (how indicators are computed)
- Strategy Usage: `src/backtester/strategies/base_strategy.py` (how strategies declare indicators)
- Built-in Examples: `IndicatorLibrary._compute_ta_indicator()` in `library.py`

---

## Quick Start Template

Copy this template to start implementing a new indicator:

```python
"""
[Description] indicator.

[Detailed explanation].
"""

import pandas as pd
from typing import Dict, Any


def your_indicator_name(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """
    Compute [indicator description] for each bar.
    
    Args:
        df: OHLCV DataFrame with datetime index
        params: Parameter dictionary
    
    Returns:
        Series with indicator values indexed by df.index
    """
    if df.empty:
        return pd.Series(dtype=float, index=df.index)
    
    period = params.get('period', 14)
    
    # TODO: Implement your indicator logic here
    
    result = pd.Series(index=df.index, dtype=float)
    return result
```

Then register it:

```python
# In __init__.py
from backtester.indicators.base import register_custom_indicator
from backtester.indicators.implementations.category.your_indicator_name import your_indicator_name

register_custom_indicator('YOUR_INDICATOR_NAME', your_indicator_name)
```

---

This guide provides everything needed to implement new indicators. Follow the steps and templates, and refer to the examples and checklist for successful implementation.

