"""
Configuration management module for the backtesting engine.

This module provides centralized configuration loading, validation, and access
for the backtesting system using a clean separation of concerns:
- ConfigLoader: Loads and merges YAML files
- ConfigValidator: Validates configuration
- ConfigAccessor: Provides type-safe access
- ConfigManager: Facade that orchestrates the above
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path

from config.core.exceptions import ConfigError
from config.core.loader import ConfigLoader
from config.core.validator import ConfigValidator, ValidationResult
from config.core.accessor import ConfigAccessor


class ConfigManager:
    """
    Centralized configuration manager for the backtesting engine.
    
    Facade that orchestrates loading, validation, and type-safe access to configuration.
    Supports profile-based configuration overrides for different testing scenarios.
    """
    
    def __init__(self, config_dir: str = 'config',
                 metadata_path: str = 'config/markets.yaml',
                 profile_name: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
            metadata_path: Path to exchange metadata file
            profile_name: Optional profile name for configuration overrides
                          (e.g., 'quick' loads config/profiles/quick.yaml)
        
        Raises:
            ConfigError: If configuration files cannot be loaded or validated
        """
        self.config_dir = config_dir
        self.metadata_path = Path(metadata_path)
        self.profile_name = profile_name
        
        # Initialize components
        self.loader = ConfigLoader(config_dir)
        self.validator = ConfigValidator()
        self.accessor = None  # Set after loading
        
        # Load configuration
        self.config = {}
        self.metadata = {}
        self._load_and_validate()
    
    def _load_and_validate(self):
        """Load and validate configuration files."""
        # Load exchange metadata
        if not self.metadata_path.exists():
            raise ConfigError(f"Metadata file not found: {self.metadata_path}")
        
        with open(self.metadata_path, 'r') as f:
            self.metadata = yaml.safe_load(f) or {}
        
        # Load all configuration files
        try:
            self.config = self.loader.load_all(profile_name=self.profile_name)
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}")
        
        # Validate configuration
        validation_result = self.validator.validate(self.config, self.metadata)
        
        if not validation_result.is_valid():
            error_messages = '\n'.join(validation_result.errors)
            raise ConfigError(f"Configuration validation failed:\n{error_messages}")
        
        # Print warnings if any
        if validation_result.warnings:
            import warnings
            for warning in validation_result.warnings:
                warnings.warn(f"Configuration warning: {warning}", UserWarning)
        
        # Initialize accessor with loaded config
        self.accessor = ConfigAccessor(self.config, self.metadata)
    
    # Expose all accessor methods through ConfigManager
    def get_strategy_name(self) -> str:
        """Get the strategy name."""
        return self.accessor.get_strategy_name()
    
    def get_strategy_config(self):
        """Get strategy configuration as typed object."""
        return self.accessor.get_strategy_config()
    
    def get_symbols(self) -> List[str]:
        """Get list of symbols to test."""
        return self.accessor.get_symbols()
    
    def get_timeframes(self) -> List[str]:
        """Get list of timeframes to test."""
        return self.accessor.get_timeframes()
    
    def get_backtest_config(self) -> Dict[str, Any]:
        """Get backtest configuration dictionary."""
        bt_config = self.accessor.get_backtest_config()
        return {
            'start_date': bt_config.start_date,
            'end_date': bt_config.end_date,
            'initial_capital': bt_config.initial_capital,
            'verbose': bt_config.verbose
        }
    
    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration dictionary."""
        trading_config = self.accessor.get_trading_config()
        return {
            'use_exchange_fees': trading_config.use_exchange_fees,
            'fee_type': trading_config.fee_type,
            'slippage': trading_config.slippage,
            'risk_per_trade': trading_config.risk_per_trade,
            'position_size': trading_config.position_size,
            'commission': trading_config.commission,
            'commission_maker': trading_config.commission_maker
        }
    
    def get_initial_capital(self) -> float:
        """Get initial capital for backtesting."""
        return self.accessor.get_initial_capital()
    
    def get_commission(self) -> float:
        """Get commission rate for backtesting."""
        return self.accessor.get_commission()
    
    def get_verbose(self) -> bool:
        """Get verbose output setting."""
        return self.accessor.get_verbose()
    
    def get_exchange_name(self) -> str:
        """Get the exchange name."""
        return self.accessor.get_exchange_name()
    
    def get_start_date(self) -> str:
        """Get the backtest start date."""
        return self.accessor.get_start_date()
    
    def get_end_date(self) -> str:
        """Get the backtest end date."""
        return self.accessor.get_end_date()
    
    def get_slippage(self) -> float:
        """Get slippage rate."""
        return self.accessor.get_slippage()
    
    def get_parallel_mode(self) -> str:
        """Get parallel execution mode: 'auto' or 'manual'."""
        return self.accessor.get_parallel_mode()
    
    def get_manual_workers(self) -> Optional[int]:
        """Get manual worker count (only used if mode='manual')."""
        return self.accessor.get_manual_workers()
    
    def get_memory_safety_factor(self) -> float:
        """Get memory safety factor for parallel execution."""
        return self.accessor.get_memory_safety_factor()
    
    def get_cpu_reserve_cores(self) -> int:
        """Get number of CPU cores to reserve for system."""
        return self.accessor.get_cpu_reserve_cores()
    
    def get_historical_start_date(self) -> str:
        """Get historical start date for data collection."""
        return self.accessor.get_historical_start_date()
    
    def is_walkforward_enabled(self) -> bool:
        """Check if walk-forward optimization is enabled."""
        return self.accessor.is_walkforward_enabled()
    
    def get_walkforward_periods(self) -> List[str]:
        """Get walk-forward period configurations (e.g., ["1Y/6M"])."""
        return self.accessor.get_walkforward_periods()
    
    def get_walkforward_fitness_functions(self) -> List[str]:
        """Get fitness function names for walk-forward optimization."""
        return self.accessor.get_walkforward_fitness_functions()
    
    def get_parameter_ranges(self) -> Dict[str, Dict[str, int]]:
        """Get parameter ranges for optimization (grid search)."""
        return self.accessor.get_parameter_ranges()
    
    def get_data_config(self) -> Dict[str, Any]:
        """Get data configuration dictionary."""
        return self.accessor.get_data_config()
    
    def get_historical_start_date(self) -> str:
        """Get historical start date for data collection."""
        return self.accessor.get_historical_start_date()
    
    def get_data_quality_config(self):
        """Get data quality configuration as typed object."""
        return self.accessor.get_data_quality_config()
    
    def get_exchange_metadata(self) -> Dict[str, Any]:
        """Get exchange metadata dictionary."""
        return self.metadata.copy()
    
    def _to_dict(self) -> Dict[str, Any]:
        """
        Serialize config for worker processes.
        
        Returns:
            Dictionary containing serializable config data
        """
        return {
            'config': self.config,
            'metadata': self.metadata,
            'profile_name': self.profile_name,
            'config_dir': self.config_dir,
            'metadata_path': str(self.metadata_path)
        }
    
    @classmethod
    def _from_dict(cls, config_dict: Dict[str, Any]) -> 'ConfigManager':
        """
        Reconstruct ConfigManager in worker process.
        
        Args:
            config_dict: Dictionary from _to_dict()
        
        Returns:
            ConfigManager instance
        """
        instance = cls.__new__(cls)
        instance.config_dir = config_dict.get('config_dir', 'config')
        instance.metadata_path = Path(config_dict.get('metadata_path', 'config/markets.yaml'))
        instance.profile_name = config_dict.get('profile_name')
        instance.config = config_dict['config']
        instance.metadata = config_dict['metadata']
        
        # Reinitialize components with loaded data
        instance.loader = ConfigLoader(instance.config_dir)
        instance.validator = ConfigValidator()
        instance.accessor = ConfigAccessor(instance.config, instance.metadata)
        
        return instance
