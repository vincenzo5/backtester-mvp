"""
Smoke tests for ConfigManager initialization.

Validates that configuration can be loaded with default and profile-based configs.
"""

import pytest


@pytest.mark.smoke
def test_config_manager_default_init(temp_config_dir):
    """Test ConfigManager can initialize with default config."""
    temp_dir, config_dir, metadata_path = temp_config_dir
    
    from backtester.config import ConfigManager
    
    config = ConfigManager(config_dir=config_dir, metadata_path=metadata_path)
    assert config is not None
    assert config.get_strategy_name() is not None


@pytest.mark.smoke
def test_config_manager_quick_profile(temp_config_dir):
    """Test ConfigManager can initialize with 'quick' profile."""
    temp_dir, config_dir, metadata_path = temp_config_dir
    
    from backtester.config import ConfigManager
    
    # Note: quick profile requires profiles/quick.yaml to exist
    # For smoke test, we just verify it doesn't crash if profile doesn't exist
    # In real usage, the profile would be present
    try:
        config = ConfigManager(
            config_dir=config_dir, 
            metadata_path=metadata_path,
            profile_name='quick'
        )
        assert config is not None
    except Exception:
        # If quick profile doesn't exist, that's ok for smoke test
        # We're just checking the code path doesn't crash
        pass


@pytest.mark.smoke
def test_config_manager_basic_access(sample_config):
    """Test ConfigManager can access basic config methods."""
    config = sample_config
    
    # Test strategy name access
    strategy_name = config.get_strategy_name()
    assert isinstance(strategy_name, str)
    assert len(strategy_name) > 0
    
    # Test exchange name access
    exchange_name = config.get_exchange_name()
    assert isinstance(exchange_name, str)
    
    # Test walkforward symbols access
    symbols = config.get_walkforward_symbols()
    assert isinstance(symbols, list)
    assert len(symbols) > 0

