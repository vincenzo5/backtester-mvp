"""
Configuration management module for the backtesting engine.

This module provides centralized configuration loading, validation, and access
for the backtesting system.
"""

import os
import yaml
from typing import Dict, List, Optional, Any


class ConfigError(Exception):
    """Raised when there's a configuration error."""
    pass


class ConfigManager:
    """
    Centralized configuration manager for the backtesting engine.
    
    Loads, validates, and provides type-safe access to configuration data.
    Supports profile-based configuration overrides for different testing scenarios.
    """
    
    def __init__(self, config_path: str = 'config/config.yaml', 
                 metadata_path: str = 'config/exchange_metadata.yaml',
                 profile_name: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to main configuration file
            metadata_path: Path to exchange metadata file
            profile_name: Optional profile name for configuration overrides
                          'quick' applies quick_test settings from config
        
        Raises:
            ConfigError: If configuration files cannot be loaded or validated
        """
        self.config_path = config_path
        self.metadata_path = metadata_path
        self.profile_name = profile_name
        self.config = {}
        self.metadata = {}
        
        self._load_and_validate()
        
        if profile_name == 'quick':
            self._merge_quick_test()
    
    def _load_and_validate(self):
        """Load and validate configuration files."""
        # Load main config
        if not os.path.exists(self.config_path):
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load exchange metadata
        if not os.path.exists(self.metadata_path):
            raise ConfigError(f"Metadata file not found: {self.metadata_path}")
        
        with open(self.metadata_path, 'r') as f:
            self.metadata = yaml.safe_load(f)
        
        # Validate required sections
        required_sections = ['exchange', 'backtest', 'trading', 'strategy']
        for section in required_sections:
            if section not in self.config:
                raise ConfigError(f"Missing required configuration section: {section}")
        
        # Set defaults for optional fields
        self.config.setdefault('data', {})
    
    def _merge_quick_test(self):
        """
        Merge quick test configuration overrides from config.yaml.
        
        Raises:
            ConfigError: If quick_test section not found in config
        """
        if 'quick_test' not in self.config:
            raise ConfigError("quick_test section not found in configuration")
        
        quick_test = self.config['quick_test']
        
        # Merge quick_test symbols and timeframes into exchange section
        if 'symbols' in quick_test:
            self.config['exchange']['symbols'] = quick_test['symbols']
        if 'timeframes' in quick_test:
            self.config['exchange']['timeframes'] = quick_test['timeframes']
        
        # Merge quick_test verbose into backtest section
        if 'verbose' in quick_test:
            self.config['backtest']['verbose'] = quick_test['verbose']
    
    def get_strategy_name(self) -> str:
        """Get the strategy name."""
        if 'name' not in self.config['strategy']:
            raise ConfigError("Missing 'name' in strategy configuration")
        return self.config['strategy']['name']
    
    def get_strategy_params(self) -> Dict[str, Any]:
        """Get strategy parameters as a dictionary."""
        if 'parameters' not in self.config['strategy']:
            return {}
        return self.config['strategy']['parameters'].copy()
    
    def get_symbols(self) -> List[str]:
        """
        Get list of symbols to test.
        
        Returns all symbols from metadata if symbols is null in config,
        otherwise returns the filtered list.
        """
        symbols = self.config['exchange'].get('symbols')
        
        if symbols is None:
            # Use all symbols from metadata
            return self.metadata.get('top_markets', [])
        elif isinstance(symbols, str):
            return [symbols]
        elif isinstance(symbols, list):
            # Validate against metadata
            valid_symbols = self.metadata.get('top_markets', [])
            return [s for s in symbols if s in valid_symbols]
        else:
            return []
    
    def get_timeframes(self) -> List[str]:
        """
        Get list of timeframes to test.
        
        Returns all timeframes from metadata if timeframes is null in config,
        otherwise returns the filtered list.
        """
        timeframes = self.config['exchange'].get('timeframes')
        
        if timeframes is None:
            # Use all timeframes from metadata
            return self.metadata.get('timeframes', [])
        elif isinstance(timeframes, str):
            return [timeframes]
        elif isinstance(timeframes, list):
            # Validate against metadata
            valid_timeframes = self.metadata.get('timeframes', [])
            return [tf for tf in timeframes if tf in valid_timeframes]
        else:
            return []
    
    def get_backtest_config(self) -> Dict[str, Any]:
        """Get backtest configuration dictionary."""
        return self.config['backtest'].copy()
    
    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration dictionary."""
        return self.config['trading'].copy()
    
    def get_initial_capital(self) -> float:
        """Get initial capital for backtesting."""
        if 'initial_capital' not in self.config['backtest']:
            raise ConfigError("Missing 'initial_capital' in backtest configuration")
        return float(self.config['backtest']['initial_capital'])
    
    def get_commission(self) -> float:
        """Get commission rate for backtesting."""
        trading_config = self.get_trading_config()
        
        # Check if we should use exchange fees
        use_exchange_fees = trading_config.get('use_exchange_fees', False)
        
        if use_exchange_fees:
            fee_type = trading_config.get('fee_type', 'taker')
            return self.metadata.get('fees', {}).get(fee_type, 0.006)
        else:
            fee_type = trading_config.get('fee_type', 'taker')
            
            if fee_type == 'maker':
                return trading_config.get('commission_maker', 0.004)
            else:
                return trading_config.get('commission', 0.006)
    
    def get_verbose(self) -> bool:
        """Get verbose output setting."""
        return self.config['backtest'].get('verbose', False)
    
    def get_exchange_name(self) -> str:
        """Get the exchange name."""
        return self.config['exchange'].get('name', 'coinbase')
    
    def get_start_date(self) -> str:
        """Get the backtest start date."""
        return self.config['backtest']['start_date']
    
    def get_end_date(self) -> str:
        """Get the backtest end date."""
        return self.config['backtest']['end_date']
    
    def get_slippage(self) -> float:
        """Get slippage rate."""
        return self.get_trading_config().get('slippage', 0.0)

