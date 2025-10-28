"""
Simple Moving Average (SMA) Crossover Strategy.

This strategy generates buy signals when the fast SMA crosses above the slow SMA,
and sell signals when the fast SMA crosses below the slow SMA.
"""

import backtrader as bt
from strategies.base_strategy import BaseStrategy


class SMACrossStrategy(BaseStrategy):
    """
    SMA Crossover Strategy.
    
    Buy when fast SMA crosses above slow SMA.
    Sell when fast SMA crosses below slow SMA.
    """
    
    params = (
        ('fast_period', 20),
        ('slow_period', 50),
        ('printlog', True),
    )
    
    def __init__(self):
        """Initialize indicators."""
        # Calculate SMAs
        self.fast_sma = bt.indicators.SMA(
            self.data.close,
            period=self.params.fast_period
        )
        
        self.slow_sma = bt.indicators.SMA(
            self.data.close,
            period=self.params.slow_period
        )
        
        # Cross signal (1 when fast crosses above slow, -1 when it crosses below)
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)
        
        # Track order for notification
        self.order = None
    
    def next(self):
        """Execute on each bar."""
        # Skip if we don't have enough data yet
        if len(self.data) < self.params.slow_period:
            return
        
        # Check if we have a pending order
        if self.order:
            return
        
        # Generate buy signal
        if not self.position:
            if self.crossover > 0:
                self.log(f'BUY CREATE, Price: {self.data.close[0]:.2f}')
                self.order = self.buy()
        
        # Generate sell signal
        else:
            if self.crossover < 0:
                self.log(f'SELL CREATE, Price: {self.data.close[0]:.2f}')
                self.order = self.sell()
    
    def notify_order(self, order):
        """Handle order notifications."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                        f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                        f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        # Reset order
        self.order = None
    
    def stop(self):
        """Called at the end of backtesting."""
        self.log(f'Fast SMA: {self.params.fast_period}, Slow SMA: {self.params.slow_period}, '
                f'Final Value: {self.broker.getvalue():.2f}')

