"""
Parameter grid generator for walk-forward optimization.

Generates parameter combinations from range specifications for grid search.
"""

from typing import Dict, List, Any
from itertools import product


def generate_parameter_values(start: int, end: int, step: int) -> List[int]:
    """
    Generate list of parameter values from range specification.
    
    Args:
        start: Starting value (inclusive)
        end: Ending value (inclusive)
        step: Step size
    
    Returns:
        List of parameter values
    
    Examples:
        >>> generate_parameter_values(10, 30, 5)
        [10, 15, 20, 25, 30]
        >>> generate_parameter_values(20, 40, 10)
        [20, 30, 40]
    """
    if start > end:
        raise ValueError(f"Start value ({start}) must be <= end value ({end})")
    
    if step <= 0:
        raise ValueError(f"Step size ({step}) must be > 0")
    
    values = []
    current = start
    while current <= end:
        values.append(current)
        current += step
    
    return values


def generate_parameter_combinations(parameter_ranges: Dict[str, Dict[str, int]]) -> List[Dict[str, int]]:
    """
    Generate all parameter combinations from range specifications.
    
    Args:
        parameter_ranges: Dictionary mapping parameter names to range specs.
                         Each range spec should have 'start', 'end', and 'step' keys.
    
    Returns:
        List of parameter dictionaries, one for each combination
    
    Example:
        >>> ranges = {
        ...     'fast_period': {'start': 10, 'end': 20, 'step': 5},
        ...     'slow_period': {'start': 30, 'end': 40, 'step': 10}
        ... }
        >>> combinations = generate_parameter_combinations(ranges)
        >>> len(combinations)
        4
        >>> combinations[0]
        {'fast_period': 10, 'slow_period': 30}
        >>> combinations[1]
        {'fast_period': 10, 'slow_period': 40}
    """
    if not parameter_ranges:
        return [{}]
    
    # Generate values for each parameter
    param_values = {}
    for param_name, range_spec in parameter_ranges.items():
        start = range_spec.get('start')
        end = range_spec.get('end')
        step = range_spec.get('step')
        
        if start is None or end is None or step is None:
            raise ValueError(
                f"Parameter range for '{param_name}' must have 'start', 'end', and 'step' keys"
            )
        
        param_values[param_name] = generate_parameter_values(start, end, step)
    
    # Generate all combinations using itertools.product
    param_names = list(param_values.keys())
    value_lists = [param_values[name] for name in param_names]
    
    combinations = []
    for combo in product(*value_lists):
        combination_dict = {param_names[i]: combo[i] for i in range(len(param_names))}
        combinations.append(combination_dict)
    
    return combinations


def count_parameter_combinations(parameter_ranges: Dict[str, Dict[str, int]]) -> int:
    """
    Count total number of parameter combinations without generating them.
    
    Useful for progress estimation.
    
    Args:
        parameter_ranges: Dictionary mapping parameter names to range specs
    
    Returns:
        Total number of combinations
    """
    if not parameter_ranges:
        return 1
    
    total = 1
    for param_name, range_spec in parameter_ranges.items():
        start = range_spec.get('start', 0)
        end = range_spec.get('end', 0)
        step = range_spec.get('step', 1)
        
        if step <= 0:
            continue
        
        count = len(generate_parameter_values(start, end, step))
        total *= count
    
    return total


