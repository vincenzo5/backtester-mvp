"""
Volatility regime filters.

Auto-registers all volatility-based filters.
"""

from backtester.filters.registry import register_filter
from backtester.filters.implementations.volatility.atr import VolatilityRegimeATR
from backtester.filters.implementations.volatility.stddev import VolatilityRegimeStdDev

# Auto-register volatility filters
register_filter(VolatilityRegimeATR)
register_filter(VolatilityRegimeStdDev)

