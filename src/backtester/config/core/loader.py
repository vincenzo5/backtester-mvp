"""
Configuration loader module.

Responsible for loading and merging configuration from multiple domain-specific YAML files.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigLoader:
    """
    Loads and merges configuration from multiple domain-specific files.
    
    Supports profile-based configuration overrides for different testing scenarios.
    """
    
    # Domain-specific config files to load
    DOMAIN_FILES = [
        'data.yaml',
        'trading.yaml',
        'strategy.yaml',
        'data_quality.yaml',
        'parallel.yaml',
        'walkforward.yaml',
        'debug.yaml',
    ]
    
    def __init__(self, config_dir: str = 'config'):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
    
    def load_all(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Load all configuration files and merge them into a single dictionary.
        
        Args:
            profile_name: Optional profile name for configuration overrides
                         (e.g., 'quick' loads config/profiles/quick.yaml)
        
        Returns:
            Dictionary containing all merged configuration
        
        Raises:
            ConfigError: If required config files cannot be loaded
        """
        # Import here to avoid circular dependency
        from backtester.config.core.exceptions import ConfigError
        config = {}
        
        # Load all domain-specific files
        for domain_file in self.DOMAIN_FILES:
            file_path = self.config_dir / domain_file
            if file_path.exists():
                domain_config = self._load_yaml(file_path)
                config.update(domain_config)
            else:
                raise ConfigError(f"Required configuration file not found: {file_path}")
        
        # Apply profile overrides if specified
        if profile_name:
            profile_config = self.load_profile(profile_name)
            config = self.merge_configs(config, profile_config)
        
        return config
    
    def load_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Load profile-specific configuration overrides.
        
        Args:
            profile_name: Name of the profile (e.g., 'quick')
        
        Returns:
            Dictionary containing profile configuration overrides
        
        Raises:
            ConfigError: If profile file not found
        """
        from backtester.config.core.exceptions import ConfigError
        profile_path = self.config_dir / 'profiles' / f'{profile_name}.yaml'
        
        if not profile_path.exists():
            raise ConfigError(f"Profile configuration file not found: {profile_path}")
        
        return self._load_yaml(profile_path)
    
    def merge_configs(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two configuration dictionaries.
        
        Overrides are applied recursively, so nested dictionaries are merged
        rather than replaced entirely.
        
        Args:
            base: Base configuration dictionary
            overrides: Configuration overrides to apply
        
        Returns:
            Merged configuration dictionary
        """
        result = base.copy()
        
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self.merge_configs(result[key], value)
            else:
                # Replace or add the value
                result[key] = value
        
        return result
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """
        Load and parse a YAML file.
        
        Args:
            file_path: Path to YAML file
        
        Returns:
            Parsed YAML content as dictionary
        
        Raises:
            ConfigError: If file cannot be loaded or parsed
        """
        from backtester.config.core.exceptions import ConfigError
        try:
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f)
                if content is None:
                    return {}
                return content
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing YAML file {file_path}: {e}")
        except IOError as e:
            raise ConfigError(f"Error reading configuration file {file_path}: {e}")

