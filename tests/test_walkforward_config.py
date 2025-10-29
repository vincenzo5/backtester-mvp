"""
Tests for walk-forward configuration management.
"""

import unittest
import tempfile
import os
import yaml
from config.manager import ConfigManager, ConfigError


class TestWalkForwardConfig(unittest.TestCase):
    """Test walk-forward configuration parsing."""
    
    def setUp(self):
        """Create temporary config file."""
        # Create minimal valid config
        self.config_data = {
            'exchange': {
                'name': 'coinbase',
                'symbols': ['BTC/USD'],
                'timeframes': ['1h']
            },
            'backtest': {
                'start_date': '2020-01-01',
                'end_date': '2021-12-31',
                'initial_capital': 100000.0,
                'verbose': False
            },
            'trading': {
                'commission': 0.006,
                'slippage': 0.0005
            },
            'strategy': {
                'name': 'sma_cross',
                'parameters': {
                    'fast_period': 20,
                    'slow_period': 50
                }
            },
            'walkforward': {
                'enabled': True,
                'periods': ['1Y/6M'],
                'fitness_function': 'np_avg_dd',
                'parameter_ranges': {
                    'fast_period': {
                        'start': 10,
                        'end': 30,
                        'step': 5
                    },
                    'slow_period': {
                        'start': 40,
                        'end': 60,
                        'step': 10
                    }
                }
            }
        }
        
        # Create temp config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'config.yaml')
        self.metadata_path = os.path.join(self.temp_dir, 'metadata.yaml')
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
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
    
    def test_walkforward_enabled(self):
        """Test walk-forward enabled check."""
        config = ConfigManager(self.config_path, self.metadata_path)
        self.assertTrue(config.is_walkforward_enabled())
    
    def test_walkforward_disabled(self):
        """Test walk-forward disabled."""
        self.config_data['walkforward']['enabled'] = False
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
        config = ConfigManager(self.config_path, self.metadata_path)
        self.assertFalse(config.is_walkforward_enabled())
    
    def test_get_walkforward_periods(self):
        """Test getting walk-forward periods."""
        config = ConfigManager(self.config_path, self.metadata_path)
        periods = config.get_walkforward_periods()
        self.assertEqual(periods, ['1Y/6M'])
    
    def test_get_fitness_function(self):
        """Test getting fitness function."""
        config = ConfigManager(self.config_path, self.metadata_path)
        fitness = config.get_walkforward_fitness_functions()
        self.assertEqual(fitness, ['np_avg_dd'])
    
    def test_get_parameter_ranges(self):
        """Test getting parameter ranges."""
        config = ConfigManager(self.config_path, self.metadata_path)
        ranges = config.get_parameter_ranges()
        
        self.assertIn('fast_period', ranges)
        self.assertIn('slow_period', ranges)
        self.assertEqual(ranges['fast_period']['start'], 10)
        self.assertEqual(ranges['fast_period']['end'], 30)
        self.assertEqual(ranges['fast_period']['step'], 5)
    
    def test_default_walkforward_settings(self):
        """Test default values when walk-forward section is missing."""
        # Remove walkforward section
        del self.config_data['walkforward']
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_data, f)
        
        config = ConfigManager(self.config_path, self.metadata_path)
        
        # Should default to disabled
        self.assertFalse(config.is_walkforward_enabled())
        # Should return empty lists/defaults
        self.assertEqual(config.get_walkforward_periods(), [])
        self.assertEqual(config.get_walkforward_fitness_functions(), ['np_avg_dd'])
        self.assertEqual(config.get_parameter_ranges(), {})


if __name__ == '__main__':
    unittest.main(verbosity=2)


