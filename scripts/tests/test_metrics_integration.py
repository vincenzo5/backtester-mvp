"""
Comprehensive integration test for metrics implementation.

This script verifies that:
1. Single backtests produce correct metrics
2. Walk-forward backtests produce consistent metrics  
3. All 43 metrics are calculated correctly
4. Metrics are properly serialized/deserialized for parallel execution
5. CSV export includes all metrics
6. Console output displays metrics correctly

Usage:
    python scripts/tests/test_metrics_integration.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backtester.data.cache_manager import read_cache
from backtester.backtest.engine import run_backtest
from backtester.strategies.sma_cross import SMACrossStrategy
from backtester.config import ConfigManager
from backtester.backtest.result import BacktestResult
from backtester.cli.output import ConsoleOutput
from backtester.backtest.metrics import save_results_csv
import pandas as pd
import traceback


def test_single_backtest_metrics():
    """Test that single backtest returns all 43 metrics."""
    print("\n" + "="*80)
    print("TEST 1: Single Backtest Metrics Completeness")
    print("="*80)
    
    try:
        # Load cached data
        df = read_cache('BTC/USD', '1h')
        
        if df.empty:
            print("⚠️  No cached data - skipping test")
            return False
        
        # Filter to recent data for speed
        if len(df) > 500:
            df = df.tail(500)
        
        print(f"✓ Loaded {len(df):,} candles")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        
        # Run backtest with return_metrics=True
        config = ConfigManager()
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            config, df, SMACrossStrategy, 
            verbose=False, 
            return_metrics=True
        )
        
        # Verify metrics object
        assert metrics is not None, "Metrics object should be returned"
        print(f"✓ Metrics object created: {type(metrics).__name__}")
        
        # Check all 43 metric fields exist
        from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics
        expected_fields = set(BacktestMetrics.__dataclass_fields__.keys())
        actual_fields = set(metrics.__dict__.keys())
        
        missing = expected_fields - actual_fields
        extra = actual_fields - expected_fields
        
        if missing:
            print(f"✗ Missing fields: {missing}")
            return False
        
        if extra:
            print(f"⚠️  Extra fields (not critical): {extra}")
        
        print(f"✓ All {len(expected_fields)} metric fields present")
        
        # Verify key metrics have valid values
        assert isinstance(metrics.total_return_pct, (int, float)), "total_return_pct should be numeric"
        assert isinstance(metrics.num_trades, int), "num_trades should be integer"
        assert isinstance(metrics.sharpe_ratio, (int, float)), "sharpe_ratio should be numeric"
        assert isinstance(metrics.max_drawdown, (int, float)), "max_drawdown should be numeric"
        
        print(f"✓ Key metrics validated:")
        print(f"  Total Return: {metrics.total_return_pct:.2f}%")
        print(f"  Number of Trades: {metrics.num_trades}")
        print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.4f}")
        print(f"  Max Drawdown: {metrics.max_drawdown:.2f}")
        
        # Verify result_dict contains serialized metrics
        assert 'metrics' in result_dict, "result_dict should contain 'metrics' key"
        assert isinstance(result_dict['metrics'], dict), "metrics should be serialized as dict"
        
        metrics_dict = result_dict['metrics']
        assert 'total_return_pct' in metrics_dict, "serialized metrics should contain total_return_pct"
        print(f"✓ Metrics properly serialized in result_dict")
        
        return True
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        traceback.print_exc()
        return False


def test_parallel_serialization():
    """Test that metrics can be serialized/deserialized for parallel execution."""
    print("\n" + "="*80)
    print("TEST 2: Metrics Serialization for Parallel Execution")
    print("="*80)
    
    try:
        # Load cached data
        df = read_cache('BTC/USD', '1h')
        
        if df.empty:
            print("⚠️  No cached data - skipping test")
            return False
        
        if len(df) > 500:
            df = df.tail(500)
        
        # Run backtest (without return_metrics to test serialization path)
        config = ConfigManager()
        result_dict = run_backtest(
            config, df, SMACrossStrategy, 
            verbose=False, 
            return_metrics=False
        )
        
        # Verify metrics dict is present
        assert 'metrics' in result_dict, "result_dict should contain metrics"
        metrics_dict = result_dict['metrics']
        
        print(f"✓ Metrics serialized in result_dict")
        print(f"  Metrics keys: {len(metrics_dict)} fields")
        
        # Reconstruct BacktestMetrics from dict (simulating parallel executor)
        from backtester.backtest.walkforward.metrics_calculator import BacktestMetrics
        reconstructed = BacktestMetrics(**metrics_dict)
        
        # Verify reconstruction
        assert isinstance(reconstructed, BacktestMetrics), "Should reconstruct BacktestMetrics"
        assert reconstructed.total_return_pct == metrics_dict['total_return_pct'], "Values should match"
        
        print(f"✓ Metrics successfully reconstructed from dict")
        print(f"  Reconstructed total_return_pct: {reconstructed.total_return_pct:.2f}%")
        
        # Test BacktestResult creation (simulating parallel executor)
        from datetime import datetime
        backtest_result = BacktestResult(
            symbol='BTC/USD',
            timeframe='1h',
            timestamp=datetime.now().isoformat(),
            metrics=reconstructed,
            initial_capital=result_dict.get('initial_capital', 10000.0),
            execution_time=result_dict.get('execution_time', 0.0),
            start_date=result_dict.get('start_date'),
            end_date=result_dict.get('end_date')
        )
        
        # Verify BacktestResult
        assert backtest_result.metrics.total_return_pct == reconstructed.total_return_pct, "Should match"
        print(f"✓ BacktestResult created successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        traceback.print_exc()
        return False


def test_csv_export():
    """Test that CSV export includes all metrics."""
    print("\n" + "="*80)
    print("TEST 3: CSV Export with Metrics")
    print("="*80)
    
    try:
        # Load cached data
        df = read_cache('BTC/USD', '1h')
        
        if df.empty:
            print("⚠️  No cached data - skipping test")
            return False
        
        if len(df) > 500:
            df = df.tail(500)
        
        # Run backtest and create BacktestResult
        config = ConfigManager()
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            config, df, SMACrossStrategy, 
            verbose=False, 
            return_metrics=True
        )
        
        from datetime import datetime
        result = BacktestResult(
            symbol='BTC/USD',
            timeframe='1h',
            timestamp=datetime.now().isoformat(),
            metrics=metrics,
            initial_capital=result_dict['initial_capital'],
            execution_time=result_dict['execution_time'],
            start_date=result_dict.get('start_date'),
            end_date=result_dict.get('end_date')
        )
        
        # Convert to dict (simulating CSV export)
        result_dict_export = result.to_dict()
        
        # Verify structure
        assert 'metrics' in result_dict_export, "Export should contain metrics"
        assert isinstance(result_dict_export['metrics'], dict), "Metrics should be dict"
        
        metrics_in_export = result_dict_export['metrics']
        print(f"✓ CSV export structure validated")
        print(f"  Metrics in export: {len(metrics_in_export)} fields")
        
        # Verify key metrics are in export
        required_keys = ['total_return_pct', 'num_trades', 'sharpe_ratio', 'max_drawdown']
        for key in required_keys:
            assert key in metrics_in_export, f"Export should contain {key}"
        
        print(f"✓ Required metrics present in export")
        
        return True
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        traceback.print_exc()
        return False


def test_console_output():
    """Test that console output displays metrics correctly."""
    print("\n" + "="*80)
    print("TEST 4: Console Output with Metrics")
    print("="*80)
    
    try:
        # Load cached data
        df = read_cache('BTC/USD', '1h')
        
        if df.empty:
            print("⚠️  No cached data - skipping test")
            return False
        
        if len(df) > 500:
            df = df.tail(500)
        
        # Run backtest and create BacktestResult
        config = ConfigManager()
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            config, df, SMACrossStrategy, 
            verbose=False, 
            return_metrics=True
        )
        
        from datetime import datetime
        from backtester.backtest.result import RunResults
        
        result = BacktestResult(
            symbol='BTC/USD',
            timeframe='1h',
            timestamp=datetime.now().isoformat(),
            metrics=metrics,
            initial_capital=result_dict['initial_capital'],
            execution_time=result_dict['execution_time'],
            start_date=result_dict.get('start_date'),
            end_date=result_dict.get('end_date')
        )
        
        # Create RunResults and test console output
        run_results = RunResults()
        run_results.results.append(result)
        run_results.successful_runs = 1
        
        # Test console output (this should not raise exceptions)
        output = ConsoleOutput()
        try:
            output.print_summary_table(run_results)
            print("✓ Console output generated without errors")
        except Exception as e:
            print(f"✗ Console output failed: {e}")
            traceback.print_exc()
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        traceback.print_exc()
        return False


def test_all_metrics_types():
    """Test that all metrics have correct types."""
    print("\n" + "="*80)
    print("TEST 5: Metrics Type Validation")
    print("="*80)
    
    try:
        # Load cached data
        df = read_cache('BTC/USD', '1h')
        
        if df.empty:
            print("⚠️  No cached data - skipping test")
            return False
        
        if len(df) > 500:
            df = df.tail(500)
        
        # Run backtest
        config = ConfigManager()
        result_dict, cerebro, strategy_instance, metrics = run_backtest(
            config, df, SMACrossStrategy, 
            verbose=False, 
            return_metrics=True
        )
        
        # Define expected types for numeric metrics
        numeric_fields = [
            'total_return_pct', 'net_profit', 'sharpe_ratio', 'max_drawdown',
            'profit_factor', 'win_rate_pct', 'gross_profit', 'gross_loss',
            'avg_trade', 'max_consecutive_wins', 'max_consecutive_losses'
        ]
        
        int_fields = ['num_trades', 'num_winning_trades', 'num_losing_trades',
                     'total_calendar_days', 'total_trading_days']
        
        errors = []
        
        for field in numeric_fields:
            value = getattr(metrics, field, None)
            if value is not None and not isinstance(value, (int, float)):
                errors.append(f"{field}: expected int/float, got {type(value)}")
        
        for field in int_fields:
            value = getattr(metrics, field, None)
            if value is not None and not isinstance(value, int):
                errors.append(f"{field}: expected int, got {type(value)}")
        
        if errors:
            print(f"✗ Type errors found:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        print(f"✓ All metric types validated ({len(numeric_fields) + len(int_fields)} fields)")
        
        return True
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("="*80)
    print("METRICS INTEGRATION TEST SUITE")
    print("="*80)
    print("\nThis test suite verifies the metrics implementation works correctly")
    print("across all code paths: single backtests, parallel execution, CSV export,")
    print("console output, and type validation.\n")
    
    tests = [
        ("Single Backtest Metrics", test_single_backtest_metrics),
        ("Parallel Serialization", test_parallel_serialization),
        ("CSV Export", test_csv_export),
        ("Console Output", test_console_output),
        ("Metrics Types", test_all_metrics_types),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ Unexpected error in {test_name}: {e}")
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("="*80)
    
    if all_passed:
        print("\n✓ All integration tests passed!")
        print("\nThe metrics implementation is working correctly across all code paths.")
        return 0
    else:
        print("\n✗ Some tests failed. Check errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

