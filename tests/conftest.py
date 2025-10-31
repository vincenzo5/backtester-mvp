"""
Shared pytest fixtures for all tests.

Provides reusable fixtures for:
- OHLCV data generation
- Configuration setup
- Component instances
- Test data utilities
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import yaml
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from backtester.config import ConfigManager
from backtester.backtest.result import BacktestResult
from backtester.backtest.walkforward.results import WalkForwardResults, WalkForwardWindowResult
from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics


@pytest.fixture
def sample_ohlcv_data():
    """
    Generate realistic OHLCV DataFrame with datetime index.
    
    Uses realistic price movements (trend + noise + volatility patterns).
    Ensures proper OHLC relationships (high >= low, high >= open/close, etc.).
    
    Default: 1000 candles, hourly frequency.
    """
    def _create_ohlcv_data(
        num_candles: int = 1000,
        start_date: Optional[datetime] = None,
        frequency: str = '1h',
        base_price: float = 50000.0,
        volatility: float = 0.02
    ) -> pd.DataFrame:
        """Create OHLCV data with specified parameters."""
        if start_date is None:
            start_date = datetime(2020, 1, 1, 0, 0, 0)
        
        # Generate datetime index
        dates = pd.date_range(start=start_date, periods=num_candles, freq=frequency)
        
        # Set seed for reproducibility using NumPy's modern random API
        rng = np.random.default_rng(42)
        
        # Generate price series with trend + noise + volatility
        n = num_candles
        # Trend component (upward trend)
        trend = np.linspace(0, base_price * 0.4, n)
        # Noise component (random walk)
        noise = rng.standard_normal(n).cumsum() * base_price * volatility * 0.1
        # Base price series
        prices = base_price + trend + noise
        
        # Generate OHLCV with realistic relationships
        closes = prices
        opens = np.roll(closes, 1)
        opens[0] = base_price
        
        # High/low spreads relative to open/close
        high_spreads = np.abs(rng.standard_normal(n) * base_price * volatility * 0.5)
        low_spreads = np.abs(rng.standard_normal(n) * base_price * volatility * 0.5)
        
        highs = np.maximum(opens, closes) + high_spreads
        lows = np.minimum(opens, closes) - low_spreads
        
        # Ensure OHLC relationships are correct
        for i in range(n):
            high = max(opens[i], closes[i], highs[i])
            low = min(opens[i], closes[i], lows[i])
            # Ensure high >= low (with small buffer if needed)
            if high <= low:
                high = low + base_price * 0.001
            highs[i] = high
            lows[i] = low
        
        # Generate volume
        volumes = rng.integers(1000000, 10000000, n)
        
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }, index=dates)
        
        return df
    
    return _create_ohlcv_data


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory with minimal valid config files."""
    temp_dir = tempfile.mkdtemp()
    config_dir = os.path.join(temp_dir, 'config')
    os.makedirs(config_dir)
    metadata_path = os.path.join(temp_dir, 'metadata.yaml')
    
    # Create domain-specific config files
    data_config = {'data': {'exchange': 'coinbase'}}
    trading_config = {'trading': {'commission': 0.006, 'slippage': 0.0005}}
    strategy_config = {
        'strategy': {
            'name': 'sma_cross',
            'parameters': {'fast_period': 10, 'slow_period': 20}
        }
    }
    walkforward_config = {
        'walkforward': {
            'start_date': '2020-01-01',
            'end_date': '2021-12-31',
            'initial_capital': 100000.0,
            'verbose': False,
            'symbols': ['BTC/USD'],
            'timeframes': ['1h'],
            'periods': ['1Y/6M'],
            'fitness_functions': ['np_avg_dd'],
            'parameter_ranges': {
                'fast_period': {'start': 10, 'end': 30, 'step': 5},
                'slow_period': {'start': 40, 'end': 60, 'step': 10}
            }
        }
    }
    data_quality_config = {
        'data_quality': {
            'weights': {
                'coverage': 0.30,
                'integrity': 0.25,
                'gaps': 0.20,
                'completeness': 0.15,
                'consistency': 0.08,
                'volume': 0.01,
                'outliers': 0.01
            },
            'thresholds': {},
            'warning_threshold': 70.0,
            'liveliness_cache_days': 30,
            'incremental_assessment': True,
            'full_assessment_schedule': 'weekly',
            'gap_filling_schedule': 'weekly'
        }
    }
    parallel_config = {'parallel': {'mode': 'auto'}}
    debug_config = {'debug': {'enabled': False, 'logging': {'level': 'INFO'}}}
    
    # Write config files
    with open(os.path.join(config_dir, 'data.yaml'), 'w') as f:
        yaml.dump(data_config, f)
    with open(os.path.join(config_dir, 'trading.yaml'), 'w') as f:
        yaml.dump(trading_config, f)
    with open(os.path.join(config_dir, 'strategy.yaml'), 'w') as f:
        yaml.dump(strategy_config, f)
    with open(os.path.join(config_dir, 'walkforward.yaml'), 'w') as f:
        yaml.dump(walkforward_config, f)
    with open(os.path.join(config_dir, 'data_quality.yaml'), 'w') as f:
        yaml.dump(data_quality_config, f)
    with open(os.path.join(config_dir, 'parallel.yaml'), 'w') as f:
        yaml.dump(parallel_config, f)
    with open(os.path.join(config_dir, 'debug.yaml'), 'w') as f:
        yaml.dump(debug_config, f)
    
    # Create minimal metadata
    metadata = {
        'exchanges': {
            'coinbase': {
                'markets': {
                    'BTC/USD': {
                        'timeframes': ['1h', '1d'],
                        'liveliness': {'status': 'live', 'verified_date': '2024-01-01'}
                    }
                }
            }
        }
    }
    with open(metadata_path, 'w') as f:
        yaml.dump(metadata, f)
    
    yield temp_dir, config_dir, metadata_path
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config(temp_config_dir):
    """Create a minimal valid ConfigManager instance."""
    temp_dir, config_dir, metadata_path = temp_config_dir
    return ConfigManager(config_dir=config_dir, metadata_path=metadata_path)


@pytest.fixture
def config_manager(sample_config):
    """Real ConfigManager instance with test config."""
    return sample_config


@pytest.fixture
def sample_strategy_params():
    """Strategy parameter dictionaries."""
    return {
        'sma_cross': {'fast_period': 10, 'slow_period': 20},
        'rsi_sma': {
            'sma_period': 20,
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70
        }
    }


@pytest.fixture
def temp_cache_dir():
    """Temporary cache directory with .cache_manifest.json."""
    temp_dir = tempfile.mkdtemp()
    cache_dir = os.path.join(temp_dir, 'data')
    os.makedirs(cache_dir)
    
    # Create empty manifest
    manifest_path = os.path.join(cache_dir, '.cache_manifest.json')
    with open(manifest_path, 'w') as f:
        import json
        json.dump({}, f)
    
    yield cache_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_backtest_result():
    """BacktestResult with realistic metrics."""
    metrics = BacktestMetrics(
        net_profit=1000.0,
        total_return_pct=10.0,
        sharpe_ratio=1.5,
        max_drawdown=500.0,
        profit_factor=2.0,
        np_avg_dd=2.0,
        gross_profit=2000.0,
        gross_loss=1000.0,
        num_trades=10,
        num_winning_trades=7,
        num_losing_trades=3,
        avg_drawdown=200.0,
        win_rate_pct=70.0,
        percent_trades_profitable=70.0,
        percent_trades_unprofitable=30.0,
        avg_trade=100.0,
        avg_profitable_trade=285.71,
        avg_unprofitable_trade=-333.33,
        largest_winning_trade=500.0,
        largest_losing_trade=-200.0,
        max_consecutive_wins=5,
        max_consecutive_losses=2,
        total_calendar_days=365,
        total_trading_days=252,
        days_profitable=150,
        days_unprofitable=102,
        percent_days_profitable=59.52,
        percent_days_unprofitable=40.48,
        max_drawdown_pct=5.0,
        max_run_up=1500.0,
        recovery_factor=2.0,
        np_max_dd=2.0,
        r_squared=0.95,
        sortino_ratio=2.0,
        monte_carlo_score=75.0,
        rina_index=10.0,
        tradestation_index=15.0,
        np_x_r2=950.0,
        np_x_pf=2000.0,
        annualized_net_profit=1000.0,
        annualized_return_avg_dd=5.0,
        percent_time_in_market=50.0,
        walkforward_efficiency=0.0
    )
    
    return BacktestResult(
        symbol='BTC/USD',
        timeframe='1h',
        timestamp=datetime.now().isoformat(),
        metrics=metrics,
        initial_capital=10000.0,
        execution_time=0.5,
        start_date='2020-01-01',
        end_date='2021-12-31'
    )


@pytest.fixture
def sample_walkforward_results(sample_backtest_result):
    """WalkForwardResults with multiple windows."""
    # Create sample window results
    window_results = []
    for i in range(3):
        # Create sample metrics for in-sample and out-of-sample
        in_sample_metrics = BacktestMetrics(
            net_profit=1000.0 + i * 100,
            total_return_pct=10.0 + i,
            sharpe_ratio=1.5,
            max_drawdown=500.0,
            profit_factor=2.0,
            np_avg_dd=2.0,
            gross_profit=2000.0,
            gross_loss=1000.0,
            num_trades=10,
            num_winning_trades=7,
            num_losing_trades=3,
            avg_drawdown=200.0,
            win_rate_pct=70.0,
            percent_trades_profitable=70.0,
            percent_trades_unprofitable=30.0,
            avg_trade=100.0,
            avg_profitable_trade=285.71,
            avg_unprofitable_trade=-333.33,
            largest_winning_trade=500.0,
            largest_losing_trade=-200.0,
            max_consecutive_wins=5,
            max_consecutive_losses=2,
            total_calendar_days=365,
            total_trading_days=252,
            days_profitable=150,
            days_unprofitable=102,
            percent_days_profitable=59.52,
            percent_days_unprofitable=40.48,
            max_drawdown_pct=5.0,
            max_run_up=1500.0,
            recovery_factor=2.0,
            np_max_dd=2.0,
            r_squared=0.95,
            sortino_ratio=2.0,
            monte_carlo_score=75.0,
            rina_index=10.0,
            tradestation_index=15.0,
            np_x_r2=950.0,
            np_x_pf=2000.0,
            annualized_net_profit=1000.0,
            annualized_return_avg_dd=5.0,
            percent_time_in_market=50.0,
            walkforward_efficiency=0.0
        )
        
        out_sample_metrics = BacktestMetrics(
            net_profit=500.0 + i * 50,
            total_return_pct=5.0 + i * 0.5,
            sharpe_ratio=1.2,
            max_drawdown=400.0,
            profit_factor=1.8,
            np_avg_dd=1.5,
            gross_profit=1000.0,
            gross_loss=500.0,
            num_trades=5,
            num_winning_trades=3,
            num_losing_trades=2,
            avg_drawdown=150.0,
            win_rate_pct=60.0,
            percent_trades_profitable=60.0,
            percent_trades_unprofitable=40.0,
            avg_trade=100.0,
            avg_profitable_trade=200.0,
            avg_unprofitable_trade=-250.0,
            largest_winning_trade=300.0,
            largest_losing_trade=-150.0,
            max_consecutive_wins=3,
            max_consecutive_losses=2,
            total_calendar_days=180,
            total_trading_days=126,
            days_profitable=80,
            days_unprofitable=46,
            percent_days_profitable=63.49,
            percent_days_unprofitable=36.51,
            max_drawdown_pct=4.0,
            max_run_up=800.0,
            recovery_factor=1.5,
            np_max_dd=1.5,
            r_squared=0.90,
            sortino_ratio=1.8,
            monte_carlo_score=70.0,
            rina_index=8.0,
            tradestation_index=12.0,
            np_x_r2=450.0,
            np_x_pf=900.0,
            annualized_net_profit=500.0,
            annualized_return_avg_dd=3.3,
            percent_time_in_market=45.0,
            walkforward_efficiency=0.5
        )
        
        window_result = WalkForwardWindowResult(
            window_index=i,
            in_sample_start=(datetime(2020, 1, 1) + timedelta(days=i * 180)).isoformat(),
            in_sample_end=(datetime(2020, 1, 1) + timedelta(days=(i + 1) * 180)).isoformat(),
            out_sample_start=(datetime(2020, 1, 1) + timedelta(days=(i + 1) * 180 + 60)).isoformat(),
            out_sample_end=(datetime(2020, 1, 1) + timedelta(days=(i + 1) * 180 + 120)).isoformat(),
            best_parameters={'fast_period': 10 + i * 5, 'slow_period': 20 + i * 10},
            in_sample_metrics=in_sample_metrics,
            out_sample_metrics=out_sample_metrics
        )
        window_results.append(window_result)
    
    results = WalkForwardResults(
        symbol='BTC/USD',
        timeframe='1h',
        period_str='1Y/6M',
        fitness_function='np_avg_dd',
        filter_config=None,
        window_results=window_results
    )
    results.calculate_aggregates()
    
    return results
