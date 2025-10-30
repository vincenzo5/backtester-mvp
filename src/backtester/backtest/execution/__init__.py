"""
Parallel execution module for hardware-aware backtesting.

This module provides hardware detection and parallel execution capabilities
for multi-market, multi-timeframe backtesting.
"""

from backtester.backtest.execution.hardware import HardwareProfile
from backtester.backtest.execution.parallel import ParallelExecutor

__all__ = ['HardwareProfile', 'ParallelExecutor']
