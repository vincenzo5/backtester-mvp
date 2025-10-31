"""
Base strategy template for creating custom trading strategies.

This module provides the base strategy class that all strategies inherit from.
It includes interfaces for declaring required indicators and third-party data sources,
which are pre-computed before backtests run for optimal performance.

Quick Start:
    from strategies.base_strategy import BaseStrategy
    from indicators.base import IndicatorSpec
    import backtrader as bt
    
    class MyStrategy(BaseStrategy):
        @classmethod
        def get_required_indicators(cls, params):
            return [
                IndicatorSpec('SMA', {'timeperiod': params['fast']}, 'SMA_fast'),
                IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
            ]
        
        def next(self):
            sma = self.data.SMA_fast[0]
            rsi = self.data.RSI_14[0]
            # Your trading logic here

Common Patterns:
    # Pattern 1: Declaring indicators
    @classmethod
    def get_required_indicators(cls, params):
        '''Declare what indicators your strategy needs'''
        return [
            IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
            IndicatorSpec('MACD', {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9}, 'MACD'),
        ]
    
    def next(self):
        # Access pre-computed indicators
        sma = self.data.SMA_20[0]
        macd = self.data.MACD_macd[0]
        signal = self.data.MACD_signal[0]
        hist = self.data.MACD_hist[0]
    
    # Pattern 2: Using third-party data
    @classmethod
    def get_required_data_sources(cls):
        from data.sources.onchain import MockOnChainProvider
        return [MockOnChainProvider()]
    
    def next(self):
        # Access aligned third-party data
        active_addresses = self.data.onchain_active_addresses[0]
        tx_count = self.data.onchain_tx_count[0]
    
    # Pattern 3: Combining indicators and data sources
    @classmethod
    def get_required_indicators(cls, params):
        return [IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14')]
    
    @classmethod
    def get_required_data_sources(cls):
        from data.sources.onchain import MockOnChainProvider
        return [MockOnChainProvider()]

Extending:
    When creating a new strategy:
    1. Inherit from BaseStrategy
    2. Implement get_required_indicators() classmethod to declare indicators
    3. Optionally implement get_required_data_sources() for third-party data
    4. Access pre-computed values via self.data in next() method
    5. All indicators/data are pre-computed before backtest starts (optimized for walk-forward)
"""

import backtrader as bt
from typing import List, Dict, Any, Optional


class BaseStrategy(bt.Strategy):
    """
    Base class for all trading strategies.
    
    Subclass this to create your own strategies. Strategies can declare required
    indicators and data sources, which are pre-computed before the backtest runs.
    
    All strategies should implement:
    - get_required_indicators(cls, params): Declare required indicators (classmethod)
    - next(): Trading logic for each bar
    - notify_order(order): Handle order execution (optional override)
    
    Optional:
    - get_required_data_sources(cls): Declare third-party data sources (classmethod)
    
    Common patterns:
    - Use self.order to track pending orders
    - Use self.params for strategy parameters
    - Use self.log() for verbose output
    - Access pre-computed indicators via self.data (e.g., self.data.SMA_20[0])
    """
    
    params = (
        ('printlog', True),  # Enable/disable logging
    )
    
    def __init__(self):
        """Initialize indicators and other components."""
        # Initialize any indicators or data here
        self.order = None  # Track pending orders
        self.trades_log = []  # Track individual trades for metrics calculation
        self.current_trade = None  # Track current open trade
    
    def next(self):
        """
        Execute on each bar/candle.
        This is where your trading logic goes.
        Override this method in your strategy.
        """
        pass
    
    def notify_order(self, order):
        """Handle order notifications."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"BaseStrategy.notify_order: status={order.status}, isbuy={order.isbuy()}, issell={order.issell()}")
        
        if order.status in [order.Submitted, order.Accepted]:
            logger.debug("BaseStrategy.notify_order: Order Submitted/Accepted, returning early")
            return
        
        if order.status in [order.Completed]:
            import pandas as pd
            # Get current datetime from data feed (backtrader format)
            try:
                # Backtrader provides datetime.datetime(0) for current bar datetime
                current_date = pd.to_datetime(self.data.datetime.datetime(0))
            except (AttributeError, TypeError):
                # Fallback if datetime access fails
                try:
                    current_date = pd.to_datetime(self.data.datetime.date(0))
                except (AttributeError, TypeError):
                    # Final fallback
                    from datetime import datetime
                    current_date = pd.to_datetime(datetime.now())
            
            logger.debug(f"BaseStrategy.notify_order: current_date = {current_date}")
            
            if order.isbuy():
                # Opening a position - start tracking a trade
                logger.debug(f"BaseStrategy.notify_order: BUY order - creating current_trade")
                self.current_trade = {
                    'entry_date': current_date,
                    'entry_price': order.executed.price,
                    'size': order.executed.size,
                    'entry_commission': order.executed.comm,
                    'entry_value': order.executed.value
                }
                logger.debug(f"BaseStrategy.notify_order: current_trade = {self.current_trade}")
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}')
            elif order.issell():
                # Closing a position - complete the trade
                logger.debug(f"BaseStrategy.notify_order: SELL order - current_trade = {self.current_trade}")
                if self.current_trade is not None:
                    exit_price = order.executed.price
                    exit_size = abs(order.executed.size)
                    exit_commission = order.executed.comm
                    exit_value = order.executed.value
                    
                    # Calculate PnL
                    # For long positions: (exit_price - entry_price) * size - commissions
                    entry_price = self.current_trade['entry_price']
                    entry_size = self.current_trade['size']
                    entry_commission = self.current_trade['entry_commission']
                    
                    # Use actual sizes to handle partial fills
                    trade_size = min(entry_size, exit_size)
                    
                    # PnL calculation: (exit - entry) * size - all commissions
                    pnl = (exit_price - entry_price) * trade_size - entry_commission - exit_commission
                    
                    # Add completed trade to log
                    trade_entry = {
                        'entry_date': self.current_trade['entry_date'],
                        'exit_date': current_date,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'size': trade_size,
                        'pnl': pnl,
                        'entry_commission': entry_commission,
                        'exit_commission': exit_commission
                    }
                    logger.debug(f"BaseStrategy.notify_order: Appending trade to trades_log: {trade_entry}")
                    logger.debug(f"BaseStrategy.notify_order: trades_log length before append: {len(self.trades_log)}, id(trades_log) = {id(self.trades_log)}, id(self) = {id(self)}")
                    self.trades_log.append(trade_entry)
                    logger.debug(f"BaseStrategy.notify_order: trades_log length after append: {len(self.trades_log)}, id(trades_log) = {id(self.trades_log)}")
                    
                    self.current_trade = None
                else:
                    logger.warning(f"BaseStrategy.notify_order: SELL order but current_trade is None!")
                
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        # Reset order tracking
        self.order = None
    
    @classmethod
    def get_required_indicators(cls, params: Dict[str, Any]) -> List:
        """
        Declare indicators required by this strategy.
        
        Override this method in your strategy to specify which indicators
        should be pre-computed before the backtest runs. This enables
        efficient computation and supports walk-forward optimization.
        
        Args:
            params: Strategy parameters from config (e.g., {'fast_period': 20})
        
        Returns:
            List of IndicatorSpec objects
        
        Example:
            @classmethod
            def get_required_indicators(cls, params):
                from indicators.base import IndicatorSpec
                return [
                    IndicatorSpec('SMA', {'timeperiod': params['fast_period']}, 'SMA_fast'),
                    IndicatorSpec('SMA', {'timeperiod': params['slow_period']}, 'SMA_slow'),
                    IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
                ]
        """
        return []
    
    @classmethod
    def get_required_data_sources(cls) -> List:
        """
        Declare third-party data sources required by this strategy.
        
        Override this method to specify data source providers that should
        fetch and align their data before the backtest runs.
        
        Returns:
            List of DataSourceProvider instances
        
        Example:
            @classmethod
            def get_required_data_sources(cls):
                from data.sources.onchain import MockOnChainProvider
                return [MockOnChainProvider()]
        
        Notes:
            - Data sources are fetched and aligned to OHLCV timeframe
            - Column names are prefixed with provider name (e.g., 'onchain_active_addresses')
            - If method not overridden, returns empty list (no external data)
        """
        return []
    
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

