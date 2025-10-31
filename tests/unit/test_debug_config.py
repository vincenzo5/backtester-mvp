"""
Tests for debug configuration system.
"""

import unittest
from pathlib import Path
import tempfile
import yaml

from backtester.config import ConfigManager
from backtester.config.core.exceptions import ConfigError


class TestDebugConfig(unittest.TestCase):
    """Test debug configuration loading and validation."""
    
    def test_debug_config_loads(self):
        """Test that debug config loads correctly."""
        config = ConfigManager()
        debug_config = config.get_debug_config()
        
        self.assertIsNotNone(debug_config)
        self.assertTrue(hasattr(debug_config, 'enabled'))
        self.assertTrue(hasattr(debug_config, 'tracing'))
        self.assertTrue(hasattr(debug_config, 'crash_reports'))
        self.assertTrue(hasattr(debug_config, 'logging'))
    
    def test_debug_config_defaults(self):
        """Test debug config provides sensible defaults."""
        # Create minimal config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Create minimal valid configs
            (config_dir / 'data.yaml').write_text(yaml.dump({'data': {'exchange': 'coinbase'}}))
            (config_dir / 'trading.yaml').write_text(yaml.dump({'trading': {'slippage': 0.0}}))
            (config_dir / 'strategy.yaml').write_text(yaml.dump({'strategy': {'name': 'sma_cross'}}))
            (config_dir / 'data_quality.yaml').write_text(yaml.dump({'data_quality': {}}))
            (config_dir / 'parallel.yaml').write_text(yaml.dump({'parallel': {}}))
            (config_dir / 'walkforward.yaml').write_text(yaml.dump({
                'walkforward': {
                    'start_date': '2022-01-01',
                    'end_date': '2023-01-01',
                    'initial_capital': 100000
                }
            }))
            (config_dir / 'debug.yaml').write_text(yaml.dump({'debug': {'enabled': True}}))
            
            # Create metadata file
            (config_dir / 'markets.yaml').write_text(yaml.dump({'exchanges': ['coinbase']}))
            
            config = ConfigManager(config_dir=str(config_dir), metadata_path=str(config_dir / 'markets.yaml'))
            debug_config = config.get_debug_config()
            
            # Should have defaults
            self.assertTrue(debug_config.enabled)
            self.assertTrue(debug_config.tracing.enabled)
            self.assertEqual(debug_config.tracing.level, 'standard')
    
    def test_debug_config_validation(self):
        """Test debug config validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Create base configs
            (config_dir / 'data.yaml').write_text(yaml.dump({'data': {'exchange': 'coinbase'}}))
            (config_dir / 'trading.yaml').write_text(yaml.dump({'trading': {'slippage': 0.0}}))
            (config_dir / 'strategy.yaml').write_text(yaml.dump({'strategy': {'name': 'sma_cross'}}))
            (config_dir / 'data_quality.yaml').write_text(yaml.dump({'data_quality': {}}))
            (config_dir / 'parallel.yaml').write_text(yaml.dump({'parallel': {}}))
            (config_dir / 'walkforward.yaml').write_text(yaml.dump({
                'walkforward': {
                    'start_date': '2022-01-01',
                    'end_date': '2023-01-01',
                    'initial_capital': 100000
                }
            }))
            
            # Invalid debug config (invalid level)
            (config_dir / 'debug.yaml').write_text(yaml.dump({
                'debug': {
                    'tracing': {'level': 'invalid_level'}
                }
            }))
            
            (config_dir / 'markets.yaml').write_text(yaml.dump({'exchanges': ['coinbase']}))
            
            with self.assertRaises(ConfigError):
                ConfigManager(config_dir=str(config_dir), metadata_path=str(config_dir / 'markets.yaml'))


if __name__ == '__main__':
    unittest.main()

