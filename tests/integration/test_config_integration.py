"""
Integration tests for configuration system.

Tests config loading → validation → access workflow.
"""

import unittest
import pytest
import tempfile
import os
import yaml
import shutil

from backtester.config import ConfigManager, ConfigError
from backtester.config.core.loader import ConfigLoader
from backtester.config.core.validator import ConfigValidator
from backtester.config.core.accessor import ConfigAccessor


@pytest.mark.integration
class TestConfigWorkflow(unittest.TestCase):
    """Test complete config workflow: load → validate → access."""
    
    def setUp(self):
        """Set up temporary config directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, 'config')
        os.makedirs(self.config_dir)
        self.metadata_path = os.path.join(self.temp_dir, 'metadata.yaml')
        
        # Create minimal valid config files
        data_config = {'data': {'exchange': 'coinbase'}}
        trading_config = {'trading': {'commission': 0.006, 'slippage': 0.0005}}
        strategy_config = {
            'strategy': {
                'name': 'sma_cross',
                'parameters': {'fast_period': 10, 'slow_period': 20}
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
                    'fast_period': {'start': 10, 'end': 30, 'step': 5}
                }
            }
        }
        data_quality_config = {
            'data_quality': {
                'weights': {
                    'coverage': 0.30,
                    'integrity': 0.25,
                    'gaps': 0.20,
                    'completeness': 0.15,
                    'consistency': 0.08,
                    'volume': 0.01,
                    'outliers': 0.01
                },
                'thresholds': {}
            }
        }
        parallel_config = {'parallel': {'mode': 'auto'}}
        debug_config = {'debug': {'enabled': False, 'logging': {'level': 'INFO'}}}
        
        # Write config files
        with open(os.path.join(self.config_dir, 'data.yaml'), 'w') as f:
            yaml.dump(data_config, f)
        with open(os.path.join(self.config_dir, 'trading.yaml'), 'w') as f:
            yaml.dump(trading_config, f)
        with open(os.path.join(self.config_dir, 'strategy.yaml'), 'w') as f:
            yaml.dump(strategy_config, f)
        with open(os.path.join(self.config_dir, 'walkforward.yaml'), 'w') as f:
            yaml.dump(walkforward_config, f)
        with open(os.path.join(self.config_dir, 'data_quality.yaml'), 'w') as f:
            yaml.dump(data_quality_config, f)
        with open(os.path.join(self.config_dir, 'parallel.yaml'), 'w') as f:
            yaml.dump(parallel_config, f)
        with open(os.path.join(self.config_dir, 'debug.yaml'), 'w') as f:
            yaml.dump(debug_config, f)
        
        # Create minimal metadata
        metadata = {
            'exchanges': {
                'coinbase': {
                    'markets': {
                        'BTC/USD': {
                            'timeframes': ['1h'],
                            'liveliness': {'status': 'live', 'verified_date': '2024-01-01'}
                        }
                    }
                }
            }
        }
        with open(self.metadata_path, 'w') as f:
            yaml.dump(metadata, f)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_config_load_validate_access(self):
        """Test complete workflow: load → validate → access."""
        # Load config
        config = ConfigManager(config_dir=self.config_dir, metadata_path=self.metadata_path)
        
        # Verify config was loaded and validated
        self.assertIsNotNone(config)
        
        # Access values through accessor methods
        strategy_name = config.get_strategy_name()
        self.assertEqual(strategy_name, 'sma_cross')
        
        walkforward_start = config.get_walkforward_start_date()
        self.assertEqual(walkforward_start, '2020-01-01')
        
        initial_capital = config.get_walkforward_initial_capital()
        self.assertEqual(initial_capital, 100000.0)
    
    def test_config_loader_validates_structure(self):
        """Test that ConfigLoader loads all domain files."""
        loader = ConfigLoader(self.config_dir)
        config = loader.load_all()
        
        # Should have all domain sections
        self.assertIn('data', config)
        self.assertIn('trading', config)
        self.assertIn('strategy', config)
        self.assertIn('walkforward', config)
    
    def test_config_validator_catches_errors(self):
        """Test that ConfigValidator catches validation errors."""
        validator = ConfigValidator()
        
        # Create invalid config (end_date before start_date)
        invalid_config = {
            'walkforward': {
                'start_date': '2021-12-31',
                'end_date': '2020-01-01',  # Invalid!
                'initial_capital': 100000.0
            }
        }
        
        metadata = {}
        result = validator.validate(invalid_config, metadata)
        
        # Should have validation errors
        self.assertFalse(result.is_valid())
        self.assertGreater(len(result.errors), 0)
    
    def test_config_accessor_type_safety(self):
        """Test that ConfigAccessor provides type-safe access."""
        config = ConfigManager(config_dir=self.config_dir, metadata_path=self.metadata_path)
        
        # Access typed config objects
        strategy_config = config.get_strategy_config()
        self.assertIsNotNone(strategy_config)
        self.assertEqual(strategy_config.name, 'sma_cross')
        
        # get_trading_config() returns a dict, not a typed object
        trading_config = config.get_trading_config()
        self.assertIsNotNone(trading_config)
        self.assertIsInstance(trading_config, dict)
        self.assertEqual(trading_config['commission'], 0.006)
    
    def test_config_update_strategy_params(self):
        """Test updating strategy parameters dynamically."""
        config = ConfigManager(config_dir=self.config_dir, metadata_path=self.metadata_path)
        
        # Update params
        config._update_strategy_parameters({'fast_period': 15, 'slow_period': 25})
        
        # Verify update
        strategy_config = config.get_strategy_config()
        self.assertEqual(strategy_config.parameters['fast_period'], 15)
        self.assertEqual(strategy_config.parameters['slow_period'], 25)

