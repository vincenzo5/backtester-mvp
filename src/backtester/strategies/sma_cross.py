"""
Simple Moving Average (SMA) Crossover Strategy.

This strategy generates buy signals when the fast SMA crosses above the slow SMA,
and sell signals when the fast SMA crosses below the slow SMA.
"""

import backtrader as bt
from backtester.strategies.base_strategy import BaseStrategy


class SMACrossStrategy(BaseStrategy):
    """Simple SMA Crossover Strategy."""
    
    params = (
        ('fast_period', 20),
        ('slow_period', 50),
        ('printlog', True),
    )
    
    def __init__(self):
        """Initialize indicators."""
        super().__init__()
        
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
        self.trade_count = 0
        self.last_position = 0  # Track position changes
        self.buy_count = 0  # Debug: count buy signals
        self.sell_count = 0  # Debug: count sell signals
    
    def next(self):
        """Execute on each bar."""
        # Skip if we don't have enough data
        if len(self.data) < self.params.slow_period:
            return
        
        # Check if we have a pending order
        if self.order:
            return
        
        # Buy signal: fast SMA crosses above slow SMA
        if not self.position:
            if self.crossover > 0:
                # Use 90% of available cash (leave room for commissions)
                cash = self.broker.getcash()
                # Calculate fractional position size (crypto supports fractional positions)
                size = (cash * 0.9) / self.data.close[0]
                # Minimum size threshold to avoid dust trades (0.0001 BTC or equivalent)
                min_size = 0.0001
                if size >= min_size:
                    self.buy_count += 1
                    self.log(f'ORDER: BUY({size:.6f}) @ ${self.data.close[0]:.2f}')
                    self.order = self.buy(size=size)
                else:
                    self.log(f'ORDER: BUY({size:.6f}) @ ${self.data.close[0]:.2f} - INSUFFICIENT CASH (below min {min_size})')
        
        # Sell signal: fast SMA crosses below slow SMA
        else:
            if self.crossover < 0:
                self.sell_count += 1
                position_size = self.position.size
                self.log(f'ORDER: SELL({position_size}) @ ${self.data.close[0]:.2f}')
                self.order = self.sell()
    
    def notify_order(self, order):
        """Handle order notifications."""
        if order.status in [order.Submitted, order.Accepted]:
            # Still call parent for consistency (though it will return early)
            super().notify_order(order)
            return
        
        if order.status in [order.Completed]:
            # Call parent first to populate trades_log
            super().notify_order(order)
            # Order details
            # Note: executed.price already includes slippage (applied by Backtrader broker)
            price = order.executed.price
            size = order.executed.size
            commission_dollar = order.executed.comm
            executed_value = order.executed.value
            
            # Count completed trades (round trips)
            # Count when we enter a position (buy order) or exit a position (sell order)
            if order.isbuy():
                # Buying - entering a position
                self.trade_count += 1
                self.last_position = abs(size)
            elif order.issell():
                # Selling - exiting a position
                self.last_position = 0
                # Don't increment count - a round trip is counted on entry
            
            # Cash and portfolio status
            cash_after = self.broker.getcash()
            portfolio_value = self.broker.getvalue()
            
            # Total cost (for buy) or proceeds (for sell)
            # Note: executed_value already includes slippage in the price, commission is separate
            total_cost = executed_value + commission_dollar if order.isbuy() else executed_value - commission_dollar
            
            if order.isbuy() and self.params.printlog:
                # BUY format: qty, price, total cost, fee %, cash, portfolio
                fee_pct = commission_dollar/executed_value*100 if executed_value > 0 else 0
                self.log(f'EXECUTION: BUY({size}) @ ${price:.2f} | Cost: ${total_cost:.2f} | Fee: {fee_pct:.2f}% | '
                        f'Cash: ${cash_after:.2f} | Value: ${portfolio_value:.2f}')
            elif order.issell() and self.params.printlog:
                # SELL format: qty (abs value), price, net after fees, fee %, cash, portfolio
                abs_size = abs(size)
                fee_pct = commission_dollar/executed_value*100 if executed_value > 0 else 0
                self.log(f'EXECUTION: SELL({abs_size}) @ ${price:.2f} | Net: ${total_cost:.2f} | Fee: {fee_pct:.2f}% | '
                        f'Cash: ${cash_after:.2f} | Value: ${portfolio_value:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # Call parent for consistency
            super().notify_order(order)
            # Additional logging if needed is handled by parent
    
    def stop(self):
        """Called at the end of backtesting."""
        if self.params.printlog:
            self.log(f'Strategy Final Value: {self.broker.getvalue():.2f}')
