"""
Strategy module for dynamic strategy loading.

This module provides a registry of trading strategies that can be dynamically
loaded based on configuration.
"""

from strategies.sma_cross import SMACrossStrategy


# Strategy registry mapping names to classes
STRATEGY_REGISTRY = {
    'sma_cross': SMACrossStrategy,
}


def get_strategy_class(strategy_name):
    """
    Get a strategy class by name.
    
    Args:
        strategy_name (str): Name of the strategy (e.g., 'sma_cross')
    
    Returns:
        class: Strategy class that can be instantiated by backtrader
    
    Raises:
        ValueError: If strategy_name is not found in registry
    """
    if strategy_name not in STRATEGY_REGISTRY:
        available = ', '.join(STRATEGY_REGISTRY.keys())
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Available strategies: {available}"
        )
    
    return STRATEGY_REGISTRY[strategy_name]


__all__ = ['get_strategy_class', 'SMACrossStrategy']
