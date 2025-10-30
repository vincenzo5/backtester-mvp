"""
Configuration core modules.

Contains the main configuration management components:
- ConfigManager: Main facade for configuration access
- ConfigLoader: Loads and merges YAML files
- ConfigValidator: Validates configuration
- ConfigAccessor: Provides type-safe access
"""

from backtester.config.core.exceptions import ConfigError
from backtester.config.core.manager import ConfigManager
from backtester.config.core.loader import ConfigLoader
from backtester.config.core.validator import ConfigValidator, ValidationResult
from backtester.config.core.accessor import ConfigAccessor

__all__ = [
    'ConfigError',
    'ConfigManager',
    'ConfigLoader',
    'ConfigValidator',
    'ValidationResult',
    'ConfigAccessor',
]

