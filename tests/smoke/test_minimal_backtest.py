"""
Smoke tests for minimal backtest execution.

Validates that a minimal backtest workflow can execute without crashing.
Uses synthetic data and existing fixtures for fast execution.
"""

import pytest


@pytest.mark.smoke
def test_prepare_backtest_data(sample_ohlcv_data, sample_config):
    """Test prepare_backtest_data with minimal data."""
    from backtester.backtest.engine import prepare_backtest_data
    from backtester.strategies.sma_cross import SMACrossStrategy
    
    # Generate minimal OHLCV data (100 candles)
    df = sample_ohlcv_data(num_candles=100)
    assert not df.empty
    assert len(df) == 100
    
    # Get strategy params
    config = sample_config
    strategy_params = config.get_strategy_config().parameters
    
    # Prepare data with indicators
    enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
    
    # Verify enriched DataFrame is valid (doesn't crash)
    assert not enriched_df.empty
    assert len(enriched_df) == len(df)  # Should preserve row count
    # At minimum, should have original OHLCV columns
    for col in ['open', 'high', 'low', 'close', 'volume']:
        assert col in enriched_df.columns
    
    # Indicators may or may not be added depending on data size and strategy params
    # For smoke test, we just verify the function completes without error


@pytest.mark.smoke
def test_run_backtest_minimal(sample_ohlcv_data, sample_config):
    """Test run_backtest with minimal data executes without crashing."""
    from backtester.backtest.engine import prepare_backtest_data, run_backtest
    from backtester.strategies.sma_cross import SMACrossStrategy
    
    # Generate minimal OHLCV data (100 candles)
    df = sample_ohlcv_data(num_candles=100)
    
    # Get config and strategy params
    config = sample_config
    strategy_params = config.get_strategy_config().parameters
    
    # Prepare data
    enriched_df = prepare_backtest_data(df, SMACrossStrategy, strategy_params)
    
    # Run backtest (may produce no trades with minimal data, that's ok)
    result = run_backtest(config, enriched_df, SMACrossStrategy, verbose=False)
    
    # Verify result structure
    assert isinstance(result, dict)
    assert 'metrics' in result
    assert 'initial_capital' in result
    assert 'execution_time' in result
    
    # Verify metrics contain expected fields
    metrics = result['metrics']
    expected_fields = [
        'net_profit',
        'total_return_pct',
        'num_trades',
        'sharpe_ratio',
        'max_drawdown'
    ]
    for field in expected_fields:
        assert field in metrics, f"Missing metric field: {field}"
    
    # Verify metrics have reasonable types
    assert isinstance(metrics['num_trades'], int)
    assert metrics['num_trades'] >= 0  # Can be 0 with minimal data
    assert isinstance(metrics['total_return_pct'], (int, float))

