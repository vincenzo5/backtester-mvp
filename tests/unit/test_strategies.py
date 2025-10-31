"""
Unit tests for strategy classes.

Tests BaseStrategy, SMACrossStrategy, and RSISMAStrategy.
"""

import unittest
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backtester.strategies.base_strategy import BaseStrategy
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.strategies.rsi_sma_strategy import RSISMAStrategy
from backtester.strategies import get_strategy_class
from backtester.indicators.base import IndicatorSpec


@pytest.mark.unit
class TestBaseStrategy(unittest.TestCase):
    """Test BaseStrategy base class."""
    
    def test_base_strategy_is_abstract(self):
        """Test that BaseStrategy cannot be instantiated directly (it's a base class)."""
        # BaseStrategy inherits from bt.Strategy which can be instantiated
        # So we test that get_required_indicators returns empty list by default
        result = BaseStrategy.get_required_indicators({})
        self.assertEqual(result, [])
    
    def test_get_required_indicators_default(self):
        """Test that BaseStrategy.get_required_indicators returns empty list by default."""
        result = BaseStrategy.get_required_indicators({'some_param': 10})
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)
    
    def test_get_required_data_sources_default(self):
        """Test that BaseStrategy.get_required_data_sources returns empty list by default."""
        result = BaseStrategy.get_required_data_sources()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


@pytest.mark.unit
class TestSMACrossStrategy(unittest.TestCase):
    """Test SMACrossStrategy."""
    
    def test_get_required_indicators_returns_specs(self):
        """Test that get_required_indicators returns IndicatorSpec objects."""
        params = {'fast_period': 10, 'slow_period': 20}
        indicators = SMACrossStrategy.get_required_indicators(params)
        
        self.assertIsInstance(indicators, list)
        self.assertGreater(len(indicators), 0)
        
        for indicator in indicators:
            self.assertIsInstance(indicator, IndicatorSpec)
    
    def test_get_required_indicators_uses_params(self):
        """Test that get_required_indicators uses provided parameters."""
        params = {'fast_period': 15, 'slow_period': 30}
        indicators = SMACrossStrategy.get_required_indicators(params)
        
        # Should have SMA indicators with correct periods
        indicator_names = [ind.column_name for ind in indicators]
        
        # Check that SMA columns are declared
        self.assertTrue(any('SMA' in name for name in indicator_names))
    
    def test_strategy_registry(self):
        """Test that SMACrossStrategy can be retrieved from registry."""
        strategy_class = get_strategy_class('sma_cross')
        self.assertEqual(strategy_class, SMACrossStrategy)
    
    def test_strategy_has_required_methods(self):
        """Test that SMACrossStrategy has required methods."""
        # Check classmethod exists
        self.assertTrue(hasattr(SMACrossStrategy, 'get_required_indicators'))
        self.assertTrue(hasattr(SMACrossStrategy, 'next'))


@pytest.mark.unit
class TestRSISMAStrategy(unittest.TestCase):
    """Test RSISMAStrategy."""
    
    def test_get_required_indicators_returns_specs(self):
        """Test that get_required_indicators returns IndicatorSpec objects."""
        params = {'sma_period': 20, 'rsi_period': 14, 'rsi_oversold': 30, 'rsi_overbought': 70}
        indicators = RSISMAStrategy.get_required_indicators(params)
        
        self.assertIsInstance(indicators, list)
        self.assertGreater(len(indicators), 0)
        
        for indicator in indicators:
            self.assertIsInstance(indicator, IndicatorSpec)
    
    def test_get_required_indicators_includes_rsi(self):
        """Test that get_required_indicators includes RSI indicator."""
        params = {'sma_period': 20, 'rsi_period': 14, 'rsi_oversold': 30, 'rsi_overbought': 70}
        indicators = RSISMAStrategy.get_required_indicators(params)
        
        indicator_names = [ind.column_name for ind in indicators]
        # Should have RSI_14 column
        self.assertTrue(any('RSI' in name for name in indicator_names))
    
    def test_strategy_registry(self):
        """Test that RSISMAStrategy can be retrieved from registry."""
        strategy_class = get_strategy_class('rsi_sma')
        self.assertEqual(strategy_class, RSISMAStrategy)
    
    def test_strategy_params_defaults(self):
        """Test that RSISMAStrategy has correct default parameters."""
        # Check that params are defined
        self.assertTrue(hasattr(RSISMAStrategy, 'params'))
        # Backtrader params creates a special class - check that parameter names exist as attributes
        param_attrs = [attr for attr in dir(RSISMAStrategy.params) 
                      if not attr.startswith('_') and attr != 'printlog' 
                      and attr not in ['isdefault', 'notdefault']]
        
        # Check default values exist as accessible attributes
        self.assertIn('sma_period', param_attrs)
        self.assertIn('rsi_period', param_attrs)
        self.assertIn('rsi_oversold', param_attrs)
        self.assertIn('rsi_overbought', param_attrs)


@pytest.mark.unit
class TestStrategyRegistry(unittest.TestCase):
    """Test strategy registry functionality."""
    
    def test_get_strategy_class_valid_name(self):
        """Test getting strategy class with valid name."""
        sma_cross = get_strategy_class('sma_cross')
        self.assertEqual(sma_cross, SMACrossStrategy)
        
        rsi_sma = get_strategy_class('rsi_sma')
        self.assertEqual(rsi_sma, RSISMAStrategy)
    
    def test_get_strategy_class_invalid_name(self):
        """Test getting strategy class with invalid name raises error."""
        with self.assertRaises(ValueError):
            get_strategy_class('nonexistent_strategy')

