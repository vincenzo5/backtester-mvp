"""
Tests for walk-forward configuration management.
"""

import unittest
import pytest
import tempfile
import os
import yaml
from backtester.config import ConfigManager, ConfigError


@pytest.mark.unit
class TestWalkForwardConfig(unittest.TestCase):
    """Test walk-forward configuration parsing."""
    
    def setUp(self):
        """Create temporary config file."""
        # Create temp config directory with domain-specific files
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        os.makedirs(self.config_dir)
        self.metadata_path = os.path.join(self.temp_dir, 'metadata.yaml')
        
        # Create domain-specific config files
        data_config = {'data': {'exchange': 'coinbase'}}
        trading_config = {'trading': {'commission': 0.006, 'slippage': 0.0005}}
        strategy_config = {
            'strategy': {
                'name': 'sma_cross',
                'parameters': {'fast_period': 20, 'slow_period': 50}
            }
        }
        walkforward_config = {
            'walkforward': {
                'start_date': '2020-01-01',
                'end_date': '2021-12-31',
                'initial_capital': 100000.0,
                'verbose': False,
                'symbols': ['BTC/USD'],
                'timeframes': ['1h'],
                'periods': ['1Y/6M'],
                'fitness_functions': ['np_avg_dd'],
                'parameter_ranges': {
                    'fast_period': {'start': 10, 'end': 30, 'step': 5},
                    'slow_period': {'start': 40, 'end': 60, 'step': 10}
                }
            }
        }
        
        data_quality_config = {'data_quality': {'weights': {}, 'thresholds': {}}}
        parallel_config = {'parallel': {'mode': 'auto'}}
        debug_config = {'debug': {'enabled': False, 'logging': {'level': 'INFO'}}}
        
        for config_dict, filename in [
            (data_config, 'data.yaml'),
            (trading_config, 'trading.yaml'),
            (strategy_config, 'strategy.yaml'),
            (walkforward_config, 'walkforward.yaml'),
            (data_quality_config, 'data_quality.yaml'),
            (parallel_config, 'parallel.yaml'),
            (debug_config, 'debug.yaml')
        ]:
            with open(os.path.join(self.config_dir, filename), 'w') as f:
                yaml.dump(config_dict, f)
        
        self.config_path = self.config_dir  # ConfigManager now expects a directory
        
        # Create minimal metadata
        metadata = {
            'top_markets': ['BTC/USD'],
            'timeframes': ['1h']
        }
        with open(self.metadata_path, 'w') as f:
            yaml.dump(metadata, f)
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_walkforward_config_access(self):
        """Test walk-forward configuration access."""
        config = ConfigManager(config_dir=self.config_path, metadata_path=self.metadata_path)
        # Walk-forward is always enabled now - no enabled flag
        self.assertEqual(config.get_walkforward_start_date(), '2020-01-01')
        self.assertEqual(config.get_walkforward_end_date(), '2021-12-31')
        self.assertEqual(config.get_walkforward_initial_capital(), 100000.0)
        self.assertEqual(config.get_walkforward_symbols(), ['BTC/USD'])
        self.assertEqual(config.get_walkforward_timeframes(), ['1h'])
    
    def test_get_walkforward_periods(self):
        """Test getting walk-forward periods."""
        config = ConfigManager(config_dir=self.config_path, metadata_path=self.metadata_path)
        periods = config.get_walkforward_periods()
        self.assertEqual(periods, ['1Y/6M'])
    
    def test_get_fitness_function(self):
        """Test getting fitness function."""
        config = ConfigManager(config_dir=self.config_path, metadata_path=self.metadata_path)
        fitness = config.get_walkforward_fitness_functions()
        self.assertEqual(fitness, ['np_avg_dd'])
    
    def test_get_parameter_ranges(self):
        """Test getting parameter ranges."""
        config = ConfigManager(config_dir=self.config_path, metadata_path=self.metadata_path)
        ranges = config.get_parameter_ranges()
        
        self.assertIn('fast_period', ranges)
        self.assertIn('slow_period', ranges)
        self.assertEqual(ranges['fast_period']['start'], 10)
        self.assertEqual(ranges['fast_period']['end'], 30)
        self.assertEqual(ranges['fast_period']['step'], 5)
    
    def test_default_walkforward_settings(self):
        """Test that walk-forward config is required."""
        # Remove walkforward.yaml file
        walkforward_path = os.path.join(self.config_dir, 'walkforward.yaml')
        if os.path.exists(walkforward_path):
            os.remove(walkforward_path)
        
        # Should raise validation error since walkforward is required
        with self.assertRaises(Exception):
            config = ConfigManager(config_dir=self.config_path, metadata_path=self.metadata_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)


