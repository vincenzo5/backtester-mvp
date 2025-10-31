"""
Filter implementations package.

This module automatically registers all filter implementations on import.
Import this module to trigger auto-registration of all filters.
"""

# Import all filter implementation packages to trigger registration
# Each package's __init__.py will register its filters

from backtester.filters.implementations import volatility  # noqa

