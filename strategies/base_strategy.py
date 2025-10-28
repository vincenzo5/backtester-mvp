"""
Base strategy template for creating custom trading strategies.
"""

import backtrader as bt


class BaseStrategy(bt.Strategy):
    """
    Base class for all trading strategies.
    
    Subclass this to create your own strategies.
    """
    
    params = (
        # Add your strategy parameters here
    )
    
    def __init__(self):
        """Initialize indicators and other components."""
        # Initialize any indicators or data here
        pass
    
    def next(self):
        """
        Execute on each bar/candle.
        This is where your trading logic goes.
        """
        # Example: Check if we have enough data
        # if len(self.data) < self.params.slow_sma_period:
        #     return
        
        # Your trading logic here
        pass
    
    def notify_order(self, order):
        """Handle order notifications."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
    
    def log(self, txt, dt=None):
        """Print formatted log message."""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

