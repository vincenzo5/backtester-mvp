"""
Filter registry for discovering and accessing filter implementations.

All filters are auto-registered when their module is imported via __init__.py files.

Quick Start:
    from backtester.filters.registry import register_filter, get_filter, list_filters
    
    # Register a filter (usually done automatically on import)
    register_filter(MyFilter)
    
    # Get a filter by name
    filter_class = get_filter('volatility_regime_atr')
    
    # List all registered filters
    all_filters = list_filters()  # ['volatility_regime_atr', ...]

Common Patterns:
    # Pattern 1: Auto-registration on import
    # In implementations/__init__.py:
    from backtester.filters.registry import register_filter
    from backtester.filters.implementations.volatility.atr import VolatilityRegimeATR
    
    register_filter(VolatilityRegimeATR)
"""

from typing import Dict, Optional, Type, List
from backtester.filters.base import BaseFilter


_FILTER_REGISTRY: Dict[str, Type[BaseFilter]] = {}


def register_filter(filter_class: Type[BaseFilter]) -> None:
    """
    Register a filter class in the registry.
    
    Args:
        filter_class: Filter class that inherits from BaseFilter
    
    Raises:
        TypeError: If filter_class doesn't inherit from BaseFilter
        ValueError: If filter doesn't have a name or name is already registered
    
    Example:
        from filters.registry import register_filter
        from filters.implementations.volatility.atr import VolatilityRegimeATR
        
        register_filter(VolatilityRegimeATR)
    """
    if not issubclass(filter_class, BaseFilter):
        raise TypeError(f"Filter must inherit from BaseFilter: {filter_class}")
    
    # Create a temporary instance to get the name (required class attribute)
    try:
        temp_instance = filter_class()
        filter_name = temp_instance.name
    except Exception as e:
        raise ValueError(f"Cannot instantiate filter class {filter_class}: {e}")
    
    if not filter_name:
        raise ValueError(f"Filter class {filter_class.__name__} must define a 'name' attribute")
    
    if filter_name in _FILTER_REGISTRY:
        raise ValueError(f"Filter '{filter_name}' is already registered (class: {_FILTER_REGISTRY[filter_name].__name__})")
    
    _FILTER_REGISTRY[filter_name] = filter_class


def get_filter(filter_name: str) -> Optional[Type[BaseFilter]]:
    """
    Get a filter class by name.
    
    Args:
        filter_name: Name of the filter (e.g., 'volatility_regime_atr')
    
    Returns:
        Filter class or None if not found
    
    Example:
        filter_class = get_filter('volatility_regime_atr')
        if filter_class:
            instance = filter_class()
            classification = instance.compute_classification(df)
    """
    return _FILTER_REGISTRY.get(filter_name)


def list_filters() -> List[str]:
    """
    List all registered filter names.
    
    Returns:
        List of filter names
    
    Example:
        filters = list_filters()
        # ['volatility_regime_atr', 'volatility_regime_stddev', ...]
    """
    return list(_FILTER_REGISTRY.keys())


def get_all_filters() -> Dict[str, Type[BaseFilter]]:
    """
    Get all registered filters.
    
    Returns:
        Dictionary mapping filter names to filter classes
    
    Example:
        all_filters = get_all_filters()
        # {'volatility_regime_atr': <class '...'>, ...}
    """
    return _FILTER_REGISTRY.copy()
