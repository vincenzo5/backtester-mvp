"""
Smoke tests for critical module imports.

Validates that all critical modules can be imported without errors.
This ensures basic module dependencies and structure are intact.
"""

import pytest
import unittest


@pytest.mark.smoke
class TestCriticalImports(unittest.TestCase):
    """Test that all critical modules can be imported."""
    
    def test_config_imports(self):
        """Test ConfigManager and ConfigError can be imported."""
        from backtester.config import ConfigManager, ConfigError
        self.assertTrue(ConfigManager is not None)
        self.assertTrue(ConfigError is not None)
    
    def test_strategy_imports(self):
        """Test strategy module imports."""
        from backtester.strategies import get_strategy_class, SMACrossStrategy
        self.assertTrue(get_strategy_class is not None)
        self.assertTrue(SMACrossStrategy is not None)
    
    def test_cache_manager_imports(self):
        """Test cache manager imports."""
        from backtester.data.cache_manager import read_cache, write_cache
        self.assertTrue(read_cache is not None)
        self.assertTrue(write_cache is not None)
    
    def test_backtest_engine_imports(self):
        """Test backtest engine imports."""
        from backtester.backtest.engine import prepare_backtest_data, run_backtest
        self.assertTrue(prepare_backtest_data is not None)
        self.assertTrue(run_backtest is not None)
    
    def test_cli_parser_imports(self):
        """Test CLI parser imports."""
        from backtester.cli.parser import parse_arguments
        self.assertTrue(parse_arguments is not None)
    
    def test_indicators_imports(self):
        """Test indicator library imports."""
        from backtester.indicators import IndicatorLibrary
        from backtester.indicators.base import IndicatorSpec
        self.assertTrue(IndicatorLibrary is not None)
        self.assertTrue(IndicatorSpec is not None)

