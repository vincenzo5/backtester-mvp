"""
Base strategy template for creating custom trading strategies.
"""

import backtrader as bt


class BaseStrategy(bt.Strategy):
    """
    Base class for all trading strategies.
    
    Subclass this to create your own strategies.
    
    All strategies should implement:
    - next(): Trading logic for each bar
    - notify_order(order): Handle order execution (optional override)
    
    Common patterns:
    - Use self.order to track pending orders
    - Use self.params for strategy parameters
    - Use self.log() for verbose output
    """
    
    params = (
        ('printlog', True),  # Enable/disable logging
    )
    
    def __init__(self):
        """Initialize indicators and other components."""
        # Initialize any indicators or data here
        self.order = None  # Track pending orders
    
    def next(self):
        """
        Execute on each bar/candle.
        This is where your trading logic goes.
        Override this method in your strategy.
        """
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
        
        # Reset order tracking
        self.order = None
    
    def log(self, txt, dt=None):
        """
        Print formatted log message.
        
        Args:
            txt (str): Log message text
            dt (datetime, optional): Timestamp for the log entry
        """
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}: {txt}')

