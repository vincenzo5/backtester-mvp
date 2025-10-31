# Filter Implementation Guide

## Purpose

This guide provides step-by-step instructions for implementing new filters in the backtester system. Follow this guide precisely when creating new filters to ensure compatibility with the filter system.

## Filter Interface Overview

All filters inherit from `BaseFilter` (defined in `src/backtester/filters/base.py`). The interface requires:

1. **Required Class Attributes:**
   - `name`: Unique string identifier (e.g., `'volatility_regime_atr'`)
   - `regimes`: List of regime labels (e.g., `['high', 'normal', 'low']`)
   - `matching`: Trade matching logic (`'entry'`, `'both'`, or `'either'`)
   - `default_params`: Dictionary of default parameters

2. **Required Method:**
   - `compute_classification(df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.Series`
     - Must return a pandas Series with regime labels
     - Series index must match `df.index` exactly
     - Series values must be from the `regimes` list

## Step-by-Step Implementation

### Step 1: Create the Filter Class File

**Location:** `src/backtester/filters/implementations/[category]/[filter_name].py`

**Category Options:**
- `volatility/` - Volatility-based filters (e.g., ATR, StdDev)
- `trend/` - Trend-based filters (e.g., MA direction)
- `volume/` - Volume-based filters
- Create a new subdirectory if needed

**Template:**

```python
"""
[Brief description of what this filter does].

[More detailed explanation if needed].
"""

import pandas as pd
import numpy as np
from backtester.filters.base import BaseFilter


class YourFilterName(BaseFilter):
    """
    [Detailed description of the filter].
    
    Classifies each bar as:
    - '[regime1]': [Description of when this regime occurs]
    - '[regime2]': [Description of when this regime occurs]
    - '[regime3]': [Description of when this regime occurs]
    
    [Additional notes about methodology or performance considerations].
    """
    
    name = 'your_filter_name'  # MUST be unique, use snake_case
    regimes = ['regime1', 'regime2', 'regime3']  # List of regime labels
    matching = 'entry'  # 'entry', 'both', or 'either'
    
    default_params = {
        'param1': 14,  # [Description of parameter]
        'param2': 0.75,  # [Description of parameter]
        # Add all parameters with sensible defaults
    }
    
    def compute_classification(self, df: pd.DataFrame, params: dict = None) -> pd.Series:
        """
        Compute [filter type] classification for each bar.
        
        Args:
            df: OHLCV DataFrame with datetime index
                Must have columns: ['open', 'high', 'low', 'close', 'volume']
            params: Optional parameter dictionary to override default_params
        
        Returns:
            Series with regime labels indexed by df.index
            Values must be one of: {self.regimes}
        
        Notes:
            - Index must match df.index exactly
            - Handle NaN values appropriately (fill with default regime)
            - Classification should be deterministic
        """
        params = params or self.default_params
        
        # CRITICAL: Handle empty DataFrame
        if df.empty:
            return pd.Series(dtype=str, index=df.index)
        
        # Extract parameters
        param1 = params.get('param1', self.default_params['param1'])
        param2 = params.get('param2', self.default_params['param2'])
        
        # YOUR CLASSIFICATION LOGIC HERE
        # Example pattern for percentile-based classification:
        # 
        # 1. Compute your indicator/measure
        #    indicator = compute_indicator(df, param1)
        # 
        # 2. Handle NaN values from rolling windows
        #    if indicator.isna().any():
        #        first_valid_idx = indicator.first_valid_index()
        #        if first_valid_idx is not None:
        #            first_valid_value = indicator.loc[first_valid_idx]
        #            indicator = indicator.fillna(first_valid_value)
        #        else:
        #            return pd.Series('normal', index=df.index)  # Default regime
        # 
        # 3. Calculate thresholds (if using percentiles)
        #    high_threshold_value = indicator.quantile(high_threshold)
        #    low_threshold_value = indicator.quantile(low_threshold)
        # 
        # 4. Classify each bar
        #    regime_series = pd.Series('normal', index=df.index, dtype=str)
        #    regime_series[indicator > high_threshold_value] = 'high'
        #    regime_series[indicator <= low_threshold_value] = 'low'
        # 
        # 5. Ensure all values are valid regimes
        #    regime_series = regime_series.fillna('normal')
        
        # TEMPLATE CODE - Replace with your logic:
        # Initialize with default regime
        regime_series = pd.Series('regime1', index=df.index, dtype=str)
        
        # Your classification logic here
        # ...
        
        # CRITICAL: Fill any remaining NaN values
        regime_series = regime_series.fillna('regime1')  # Use first regime as default
        
        # CRITICAL: Verify all values are valid regimes
        invalid_regimes = set(regime_series) - set(self.regimes)
        if invalid_regimes:
            raise ValueError(f"Invalid regime values found: {invalid_regimes}. Must be one of {self.regimes}")
        
        return regime_series
```

### Step 2: Register the Filter

**Location:** Update `src/backtester/filters/implementations/[category]/__init__.py`

**If category already exists:**

```python
"""
[Category description] filters.

Auto-registers all [category]-based filters.
"""

from backtester.filters.registry import register_filter
from backtester.filters.implementations.[category].existing_filter import ExistingFilter
from backtester.filters.implementations.[category].your_filter_name import YourFilterName

# Auto-register filters
register_filter(ExistingFilter)
register_filter(YourFilterName)  # ADD THIS LINE
```

**If creating a new category:**

1. Create `src/backtester/filters/implementations/[category]/__init__.py`:
```python
"""
[Category description] filters.

Auto-registers all [category]-based filters.
"""

from backtester.filters.registry import register_filter
from backtester.filters.implementations.[category].your_filter_name import YourFilterName

# Auto-register filters
register_filter(YourFilterName)
```

2. Update `src/backtester/filters/implementations/__init__.py` to import the new category:

```python
"""
Filter implementations package.

This module automatically registers all filter implementations on import.
Import this module to trigger auto-registration of all filters.
"""

# Import all filter implementation packages to trigger registration
from backtester.filters.implementations import volatility  # noqa
from backtester.filters.implementations import [category]  # ADD THIS LINE (replace [category] with your category name)
```

### Step 3: Reference Implementation Examples

Study these existing implementations for patterns:

**ATR-based Volatility Filter:**
- File: `src/backtester/filters/implementations/volatility/atr.py`
- Pattern: Rolling indicator → Percentile thresholds → Classification
- Regimes: `['high', 'normal', 'low']`

**StdDev-based Volatility Filter:**
- File: `src/backtester/filters/implementations/volatility/stddev.py`
- Pattern: Rolling indicator on returns → Percentile thresholds → Classification
- Regimes: `['high', 'normal', 'low']`

### Step 4: Key Implementation Requirements

**CRITICAL Requirements:**

1. **Index Matching:** Returned Series index MUST match `df.index` exactly
   ```python
   # CORRECT
   return pd.Series(regimes, index=df.index)
   
   # WRONG
   return pd.Series(regimes)  # Missing index
   ```

2. **Valid Regimes:** All Series values MUST be from the `regimes` list
   ```python
   # Add validation
   invalid = set(regime_series) - set(self.regimes)
   if invalid:
       raise ValueError(f"Invalid regimes: {invalid}")
   ```

3. **NaN Handling:** Handle NaN values from rolling windows
   ```python
   if indicator.isna().any():
       first_valid_idx = indicator.first_valid_index()
       if first_valid_idx:
           indicator = indicator.fillna(indicator.loc[first_valid_idx])
       else:
           return pd.Series('default_regime', index=df.index)
   ```

4. **Empty DataFrame:** Always handle empty input
   ```python
   if df.empty:
       return pd.Series(dtype=str, index=df.index)
   ```

5. **Name Uniqueness:** Filter name MUST be unique across all filters
   - Use snake_case: `'volatility_regime_atr'`
   - Be descriptive: `'your_category_your_measure'`

6. **Matching Logic:**
   - `'entry'`: Filter based on regime at trade entry only
   - `'both'`: Both entry AND exit must match target regime
   - `'either'`: Either entry OR exit must match target regime

## Testing Your Filter

### Smoke Test

Create `tests/smoke/test_[filter_name]_init.py`:

```python
"""Smoke tests for [FilterName] initialization."""

import unittest
import pytest
from backtester.filters.registry import get_filter

@pytest.mark.smoke
class Test[FilterName]Initialization(unittest.TestCase):
    """Test [FilterName] can be instantiated."""
    
    def test_filter_can_be_imported(self):
        """Filter class can be imported."""
        from backtester.filters.implementations.[category].[filter_name] import [FilterName]
        self.assertIsNotNone([FilterName])
    
    def test_filter_can_be_instantiated(self):
        """Filter can be instantiated without errors."""
        filter_class = get_filter('[filter_name]')
        self.assertIsNotNone(filter_class)
        instance = filter_class()
        self.assertEqual(instance.name, '[filter_name]')
    
    def test_filter_has_required_attributes(self):
        """Filter has all required class attributes."""
        filter_class = get_filter('[filter_name]')
        instance = filter_class()
        
        self.assertTrue(hasattr(instance, 'name'))
        self.assertTrue(hasattr(instance, 'regimes'))
        self.assertTrue(hasattr(instance, 'matching'))
        self.assertTrue(hasattr(instance, 'default_params'))
        self.assertIn(instance.matching, ['entry', 'both', 'either'])
```

### Unit Test

Create `tests/unit/test_[filter_name].py`:

```python
"""Unit tests for [FilterName] filter."""

import unittest
import pytest
import pandas as pd
from backtester.filters.registry import get_filter
from tests.conftest import sample_ohlcv_data

@pytest.mark.unit
class Test[FilterName](unittest.TestCase):
    """Test [FilterName] classification logic."""
    
    def setUp(self):
        """Set up test environment."""
        self.filter_class = get_filter('[filter_name]')
        self.filter_instance = self.filter_class()
        self.df = sample_ohlcv_data(num_candles=100)
    
    def test_compute_classification_returns_series(self):
        """compute_classification returns pandas Series."""
        result = self.filter_instance.compute_classification(self.df)
        self.assertIsInstance(result, pd.Series)
    
    def test_classification_index_matches_dataframe(self):
        """Classification Series index matches DataFrame index."""
        result = self.filter_instance.compute_classification(self.df)
        pd.testing.assert_index_equal(result.index, self.df.index)
    
    def test_classification_values_are_valid_regimes(self):
        """All classification values are from regimes list."""
        result = self.filter_instance.compute_classification(self.df)
        invalid = set(result) - set(self.filter_instance.regimes)
        self.assertEqual(len(invalid), 0, f"Invalid regimes: {invalid}")
    
    def test_empty_dataframe_handling(self):
        """Empty DataFrame returns empty Series with correct index."""
        empty_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        empty_df.index = pd.DatetimeIndex([])
        result = self.filter_instance.compute_classification(empty_df)
        self.assertEqual(len(result), 0)
    
    def test_custom_parameters(self):
        """Filter accepts custom parameters."""
        custom_params = {'param1': 20, 'param2': 0.8}
        result = self.filter_instance.compute_classification(self.df, params=custom_params)
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(self.df))
```

## Usage

Once implemented and registered, your filter can be used in walk-forward optimization:

**Configuration (`config/walkforward.yaml`):**

```yaml
walkforward:
  filters:
    - volatility_regime_atr
    - your_filter_name  # Your new filter
```

The filter system will:
1. Compute your filter's classification once per dataset
2. Add the classification as a column to the DataFrame
3. Generate filter configurations (cartesian product of all regimes + baseline)
4. Apply filters to trades post-execution based on matching logic

## Common Patterns

### Pattern 1: Percentile-Based Three-Regime Classification

```python
# Compute indicator
indicator = compute_indicator(df, params)

# Handle NaN
if indicator.isna().any():
    first_valid_idx = indicator.first_valid_index()
    if first_valid_idx:
        indicator = indicator.fillna(indicator.loc[first_valid_idx])
    else:
        return pd.Series('normal', index=df.index)

# Percentile thresholds
high_threshold_value = indicator.quantile(params['high_threshold'])
low_threshold_value = indicator.quantile(params['low_threshold'])

# Classify
regime_series = pd.Series('normal', index=df.index, dtype=str)
regime_series[indicator > high_threshold_value] = 'high'
regime_series[indicator <= low_threshold_value] = 'low'
```

### Pattern 2: Binary Classification

```python
# Compute indicator
indicator = compute_indicator(df, params)

# Threshold (can be absolute or percentile-based)
threshold = indicator.quantile(params['threshold']) if params.get('use_percentile') else params['threshold']

# Binary classification
regime_series = pd.Series('low', index=df.index, dtype=str)
regime_series[indicator > threshold] = 'high'
```

### Pattern 3: Multi-Threshold Classification

```python
# Compute indicator
indicator = compute_indicator(df, params)

# Multiple thresholds
thresholds = sorted([
    indicator.quantile(params['threshold1']),
    indicator.quantile(params['threshold2']),
    indicator.quantile(params['threshold3']),
])

# Multi-regime classification
regime_series = pd.Series('low', index=df.index, dtype=str)
regime_series[(indicator > thresholds[0]) & (indicator <= thresholds[1])] = 'medium'
regime_series[indicator > thresholds[1]] = 'high'
```

## Checklist

Before submitting your filter implementation:

- [ ] Filter class inherits from `BaseFilter`
- [ ] All required class attributes defined (`name`, `regimes`, `matching`, `default_params`)
- [ ] `compute_classification()` method implemented
- [ ] Filter registered in appropriate `__init__.py`
- [ ] Category `__init__.py` imports and registers filter
- [ ] Main `implementations/__init__.py` imports category (if new category)
- [ ] Filter name is unique and uses snake_case
- [ ] Returned Series index matches `df.index` exactly
- [ ] All Series values are from `regimes` list
- [ ] NaN values handled appropriately
- [ ] Empty DataFrame handled
- [ ] Smoke tests created
- [ ] Unit tests created
- [ ] Docstrings added to class and method
- [ ] Code follows existing patterns

## Files to Create/Modify

1. **Create:** `src/backtester/filters/implementations/[category]/[filter_name].py`
2. **Modify:** `src/backtester/filters/implementations/[category]/__init__.py`
3. **Modify:** `src/backtester/filters/implementations/__init__.py` (if new category)
4. **Create:** `tests/smoke/test_[filter_name]_init.py`
5. **Create:** `tests/unit/test_[filter_name].py`

## Reference Files

- Base Interface: `src/backtester/filters/base.py`
- Registry: `src/backtester/filters/registry.py`
- Example: `src/backtester/filters/implementations/volatility/atr.py`
- Example: `src/backtester/filters/implementations/volatility/stddev.py`
- Applicator: `src/backtester/filters/applicator.py` (how filters are applied)

---

## Quick Start Template

Copy this template to start implementing a new filter:

```python
"""
[Description] filter.

[Detailed explanation].
"""

import pandas as pd
import numpy as np
from backtester.filters.base import BaseFilter


class YourFilterName(BaseFilter):
    """[Description]."""
    
    name = 'your_filter_name'
    regimes = ['regime1', 'regime2']  # Adjust as needed
    matching = 'entry'  # 'entry', 'both', or 'either'
    
    default_params = {
        'param1': 14,
    }
    
    def compute_classification(self, df: pd.DataFrame, params: dict = None) -> pd.Series:
        """Compute classification for each bar."""
        params = params or self.default_params
        
        if df.empty:
            return pd.Series(dtype=str, index=df.index)
        
        # TODO: Implement your classification logic here
        
        regime_series = pd.Series('regime1', index=df.index, dtype=str)
        regime_series = regime_series.fillna('regime1')
        
        return regime_series
```

---

This guide provides everything needed to implement new filters. Follow the steps and templates, and refer to the examples and checklist for successful implementation.

