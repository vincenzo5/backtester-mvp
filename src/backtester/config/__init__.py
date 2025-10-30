"""
Configuration package.

Provides centralized configuration management for the backtesting engine.

Main entry point:
    from config import ConfigManager
    
    config = ConfigManager()
    exchange = config.get_exchange_name()
"""

# Re-export main components for backward compatibility and convenience
from backtester.config.core import (
    ConfigError,
    ConfigManager,
    ConfigLoader,
    ConfigValidator,
    ValidationResult,
    ConfigAccessor,
)

__all__ = [
    'ConfigError',
    'ConfigManager',
    'ConfigLoader',
    'ConfigValidator',
    'ValidationResult',
    'ConfigAccessor',
]

