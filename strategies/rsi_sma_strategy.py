"""
RSI + SMA Combined Strategy Example.

This strategy demonstrates how to use the new indicator library system.
It combines RSI (Relative Strength Index) and SMA (Simple Moving Average)
to generate trading signals.

Quick Start:
    This strategy is automatically available when registered in strategies/__init__.py
    
    Config example:
        strategy:
          name: rsi_sma
          parameters:
            sma_period: 20
            rsi_period: 14
            rsi_oversold: 30
            rsi_overbought: 70
    
    Run backtest:
        python main.py  # Uses config.yaml settings

Common Patterns:
    # Pattern 1: Declaring indicators
    @classmethod
    def get_required_indicators(cls, params):
        from indicators.base import IndicatorSpec
        return [
            IndicatorSpec('SMA', {'timeperiod': params['sma_period']}, 'SMA_20'),
            IndicatorSpec('RSI', {'timeperiod': params['rsi_period']}, 'RSI_14'),
        ]
    
    # Pattern 2: Accessing pre-computed indicators
    def next(self):
        rsi = self.data.RSI_14[0]  # Current RSI value
        
        # Buy when oversold (mean reversion)
        if rsi < 30:
            self.buy()
        
        # Sell when overbought (mean reversion)
        elif rsi > 70:
            self.sell()
    
    # Pattern 3: Combining indicators with third-party data
    @classmethod
    def get_required_data_sources(cls):
        from data.sources.onchain import MockOnChainProvider
        return [MockOnChainProvider()]
    
    def next(self):
        rsi = self.data.RSI_14[0]
        active_addresses = self.data.onchain_active_addresses[0]
        
        # Add on-chain confirmation to RSI signal
        if rsi < 30 and active_addresses > threshold:
            self.buy()

Strategy Logic:
    Buy Signal:
        - RSI < oversold threshold (default: 30) - Mean reversion buy
        - Not already in a position
    
    Sell Signal:
        - RSI > overbought threshold (default: 70) - Mean reversion sell
        - Currently holding a position
    
    This is a classic mean reversion strategy:
    - Buy when RSI is oversold (expecting bounce up)
    - Sell when RSI is overbought (expecting pullback down)

Extending:
    To modify this strategy:
    1. Change indicator parameters via config.yaml
    2. Add more indicators in get_required_indicators()
    3. Add data sources in get_required_data_sources()
    4. Modify trading logic in next()
    
    Example: Add MACD confirmation
        @classmethod
        def get_required_indicators(cls, params):
            return [
                IndicatorSpec('SMA', {...}, 'SMA_20'),
                IndicatorSpec('RSI', {...}, 'RSI_14'),
                IndicatorSpec('MACD', {...}, 'MACD'),  # New!
            ]
        
        def next(self):
            macd_line = self.data.MACD_macd[0]
            signal_line = self.data.MACD_signal[0]
            
            if rsi < 30 and macd_line > signal_line:  # MACD bullish
                self.buy()
"""

import pandas as pd
from strategies.base_strategy import BaseStrategy
from indicators.base import IndicatorSpec


class RSISMAStrategy(BaseStrategy):
    """
    RSI + SMA Combined Strategy.
    
    This strategy uses RSI for overbought/oversold signals and SMA for trend confirmation.
    It demonstrates the new indicator library system with pre-computed indicators.
    
    Parameters:
        sma_period: Period for SMA calculation (default: 20)
        rsi_period: Period for RSI calculation (default: 14)
        rsi_oversold: RSI threshold for oversold (default: 30)
        rsi_overbought: RSI threshold for overbought (default: 70)
        printlog: Enable/disable logging
    """
    
    params = (
        ('sma_period', 20),
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('printlog', True),
    )
    
    @classmethod
    def get_required_indicators(cls, params):
        """
        Declare required indicators for this strategy.
        
        Returns list of IndicatorSpec objects. These will be pre-computed
        before the backtest runs, making it efficient for walk-forward optimization.
        """
        from indicators.base import IndicatorSpec
        
        return [
            IndicatorSpec(
                'SMA',
                {'timeperiod': params.get('sma_period', 20)},
                'SMA_20'
            ),
            IndicatorSpec(
                'RSI',
                {'timeperiod': params.get('rsi_period', 14)},
                'RSI_14'
            ),
        ]
    
    def __init__(self):
        """Initialize strategy."""
        super().__init__()
        self.order = None
        self.buy_count = 0
        self.sell_count = 0
    
    def next(self):
        """
        Execute trading logic on each bar.
        
        Access pre-computed indicators via self.data:
        - self.data.SMA_20[0] - Current SMA value
        - self.data.RSI_14[0] - Current RSI value
        """
        # Skip if we don't have enough data for indicators
        if len(self.data) < max(self.params.sma_period, self.params.rsi_period):
            return
        
        # Skip if we have a pending order
        if self.order:
            return
        
        # Access pre-computed indicators
        sma = self.data.SMA_20[0]
        rsi = self.data.RSI_14[0]
        current_price = self.data.close[0]
        
        # Check for NaN values (indicators might not be computed for early bars)
        if pd.isna(rsi):
            return
        
        # Buy signal: RSI oversold (mean reversion strategy)
        # When RSI is oversold, price has fallen too far - expect bounce
        if not self.position:
            if rsi < self.params.rsi_oversold:
                # Use 90% of available cash
                cash = self.broker.getcash()
                size = int((cash * 0.9) / current_price)
                if size > 0:
                    self.buy_count += 1
                    self.log(f'BUY SIGNAL: RSI={rsi:.2f} (oversold), Price=${current_price:.2f}')
                    self.order = self.buy(size=size)
        
        # Sell signal: RSI overbought (mean reversion strategy)
        # When RSI is overbought, price has risen too far - expect pullback
        else:
            if rsi > self.params.rsi_overbought:
                self.sell_count += 1
                position_size = self.position.size
                self.log(f'SELL SIGNAL: RSI={rsi:.2f} (overbought), Price=${current_price:.2f}')
                self.order = self.sell()
    
    def stop(self):
        """Called at the end of backtesting."""
        if self.params.printlog:
            self.log(f'Strategy Final Value: {self.broker.getvalue():.2f}')
            self.log(f'Total Buy Signals: {self.buy_count}')
            self.log(f'Total Sell Signals: {self.sell_count}')
