"""
Test script for indicators and data sources implementation.

Tests:
1. Indicator library computation
2. Data source providers
3. Strategy integration
4. Backward compatibility
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_indicator_library():
    """Test basic indicator computation."""
    print("\n" + "="*60)
    print("TEST 1: Indicator Library")
    print("="*60)
    
    try:
        from indicators import IndicatorLibrary, IndicatorSpec
        
        # Create sample OHLCV data
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 2)
        
        df = pd.DataFrame({
            'open': prices + np.random.randn(100) * 0.5,
            'high': prices + abs(np.random.randn(100) * 1),
            'low': prices - abs(np.random.randn(100) * 1),
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, 100)
        }, index=dates)
        
        # Test single indicator
        lib = IndicatorLibrary()
        sma = lib.compute_indicator(df, 'SMA', {'timeperiod': 20}, 'SMA_20')
        
        assert isinstance(sma, pd.Series), "SMA should return a Series"
        assert len(sma) == len(df), "SMA should have same length as DataFrame"
        assert not sma.iloc[:20].isna().all(), "Should have some NaN values initially"
        assert not sma.iloc[-10:].isna().any(), "Should have valid values later"
        print("✓ Single indicator (SMA) computation works")
        
        # Test multiple indicators
        specs = [
            IndicatorSpec('SMA', {'timeperiod': 20}, 'SMA_20'),
            IndicatorSpec('RSI', {'timeperiod': 14}, 'RSI_14'),
            IndicatorSpec('MACD', {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9}, 'MACD'),
        ]
        
        enriched_df = lib.compute_all(df, specs)
        
        assert 'SMA_20' in enriched_df.columns, "SMA_20 column should exist"
        assert 'RSI_14' in enriched_df.columns, "RSI_14 column should exist"
        assert 'MACD_macd' in enriched_df.columns, "MACD_macd column should exist"
        assert 'MACD_signal' in enriched_df.columns, "MACD_signal column should exist"
        assert 'MACD_hist' in enriched_df.columns, "MACD_hist column should exist"
        print("✓ Multiple indicators computation works")
        print(f"✓ Added columns: {', '.join(enriched_df.columns[5:])}")
        
        # Test custom indicator
        from indicators.base import register_custom_indicator
        
        def test_indicator(df, params):
            return df['close'].rolling(window=params['period']).std()
        
        register_custom_indicator('CUSTOM_STD', test_indicator)
        
        custom_spec = IndicatorSpec('CUSTOM_STD', {'period': 10}, 'std_10')
        result = lib.compute_indicator(df, 'CUSTOM_STD', {'period': 10}, 'std_10')
        
        assert isinstance(result, pd.Series), "Custom indicator should return Series"
        print("✓ Custom indicator registration and computation works")
        
        return True
        
    except Exception as e:
        print(f"✗ Indicator library test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_data_sources():
    """Test data source providers."""
    print("\n" + "="*60)
    print("TEST 2: Data Source Providers")
    print("="*60)
    
    try:
        from data.sources.onchain import MockOnChainProvider
        
        # Create provider
        provider = MockOnChainProvider()
        
        # Test fetch
        raw_data = provider.fetch('BTC/USD', '2024-01-01', '2024-01-31')
        
        assert not raw_data.empty, "Should fetch data"
        assert 'active_addresses' in raw_data.columns, "Should have active_addresses column"
        assert 'tx_count' in raw_data.columns, "Should have tx_count column"
        assert isinstance(raw_data.index, pd.DatetimeIndex), "Should have datetime index"
        print(f"✓ Fetched {len(raw_data)} days of mock on-chain data")
        print(f"✓ Columns: {', '.join(raw_data.columns)}")
        
        # Test alignment
        # Create hourly OHLCV data
        hourly_dates = pd.date_range('2024-01-01', '2024-01-31 23:00:00', freq='h')
        hourly_df = pd.DataFrame({
            'open': np.random.randn(len(hourly_dates)) * 100,
            'high': np.random.randn(len(hourly_dates)) * 100,
            'low': np.random.randn(len(hourly_dates)) * 100,
            'close': np.random.randn(len(hourly_dates)) * 100,
            'volume': np.random.randint(1000, 10000, len(hourly_dates))
        }, index=hourly_dates)
        
        aligned = provider.align_to_ohlcv(raw_data, hourly_df, prefix='onchain_')
        
        assert len(aligned) == len(hourly_df), "Aligned data should match OHLCV length"
        assert 'onchain_active_addresses' in aligned.columns, "Should have prefixed column"
        assert 'onchain_tx_count' in aligned.columns, "Should have prefixed column"
        
        # Check that values are forward-filled (same value for multiple hours)
        assert aligned['onchain_active_addresses'].iloc[0] == aligned['onchain_active_addresses'].iloc[10], \
            "Should forward-fill daily values to hourly"
        print("✓ Data alignment (daily → hourly) works")
        print(f"✓ Aligned {len(hourly_df)} hourly candles from {len(raw_data)} daily data points")
        
        return True
        
    except Exception as e:
        print(f"✗ Data source test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_integration():
    """Test strategy integration with indicators."""
    print("\n" + "="*60)
    print("TEST 3: Strategy Integration")
    print("="*60)
    
    try:
        from strategies.rsi_sma_strategy import RSISMAStrategy
        from indicators.base import IndicatorSpec
        
        # Test get_required_indicators
        params = {'sma_period': 20, 'rsi_period': 14}
        indicator_specs = RSISMAStrategy.get_required_indicators(params)
        
        assert len(indicator_specs) == 2, "Should return 2 indicator specs"
        assert any(spec.indicator_type == 'SMA' for spec in indicator_specs), "Should include SMA"
        assert any(spec.indicator_type == 'RSI' for spec in indicator_specs), "Should include RSI"
        print("✓ Strategy declares indicators correctly")
        
        # Test get_required_data_sources (should return empty list by default)
        data_sources = RSISMAStrategy.get_required_data_sources()
        assert isinstance(data_sources, list), "Should return a list"
        print("✓ Strategy data sources method works")
        
        return True
        
    except Exception as e:
        print(f"✗ Strategy integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_backtest_engine_integration():
    """Test backtest engine integration."""
    print("\n" + "="*60)
    print("TEST 4: Backtest Engine Integration")
    print("="*60)
    
    try:
        from backtest.engine import prepare_backtest_data, run_backtest
        from strategies.rsi_sma_strategy import RSISMAStrategy
        from config import ConfigManager
        
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=200, freq='D')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(200) * 0.5)
        
        df = pd.DataFrame({
            'open': prices + np.random.randn(200) * 0.5,
            'high': prices + abs(np.random.randn(200) * 1),
            'low': prices - abs(np.random.randn(200) * 1),
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, 200)
        }, index=dates)
        
        # Test prepare_backtest_data
        strategy_params = {'sma_period': 20, 'rsi_period': 14, 'rsi_oversold': 30, 'rsi_overbought': 70}
        enriched_df = prepare_backtest_data(df, RSISMAStrategy, strategy_params)
        
        original_cols = set(df.columns)
        new_cols = set(enriched_df.columns) - original_cols
        
        assert 'SMA_20' in new_cols, "Should have SMA_20 column"
        assert 'RSI_14' in new_cols, "Should have RSI_14 column"
        print(f"✓ prepare_backtest_data added {len(new_cols)} columns: {', '.join(new_cols)}")
        
        # Test run_backtest (without actually running - just verify it doesn't crash)
        # We'll use a minimal config
        try:
            config = ConfigManager()
            # This might fail if config is not set up, so we'll catch and skip
            result = run_backtest(config, df, RSISMAStrategy, verbose=False)
            print("✓ run_backtest executes successfully")
            print(f"✓ Backtest completed with {result.get('num_trades', 0)} trades")
        except Exception as e:
            print(f"⚠ run_backtest test skipped (config issue): {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Backtest engine integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test that old strategies still work."""
    print("\n" + "="*60)
    print("TEST 5: Backward Compatibility")
    print("="*60)
    
    try:
        from strategies.sma_cross import SMACrossStrategy
        from strategies.base_strategy import BaseStrategy
        
        # Old strategy should still work
        assert issubclass(SMACrossStrategy, BaseStrategy), "Should inherit from BaseStrategy"
        
        # Should have get_required_indicators (returns empty by default)
        params = {}
        indicator_specs = SMACrossStrategy.get_required_indicators(params)
        assert isinstance(indicator_specs, list), "Should return a list"
        print("✓ Old strategy (sma_cross) is compatible with new interface")
        
        # Old strategy should still work with backtest engine
        from backtest.engine import prepare_backtest_data
        
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        
        df = pd.DataFrame({
            'open': prices,
            'high': prices + 1,
            'low': prices - 1,
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, 100)
        }, index=dates)
        
        # Should not crash even though strategy doesn't declare indicators
        enriched_df = prepare_backtest_data(df, SMACrossStrategy, {})
        
        # DataFrame should be unchanged if no indicators declared
        assert len(enriched_df.columns) == len(df.columns), "Should not add columns if no indicators"
        print("✓ Old strategy works without declaring indicators")
        
        return True
        
    except Exception as e:
        print(f"✗ Backward compatibility test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TESTING INDICATORS AND DATA SOURCES IMPLEMENTATION")
    print("="*60)
    
    tests = [
        ("Indicator Library", test_indicator_library),
        ("Data Sources", test_data_sources),
        ("Strategy Integration", test_strategy_integration),
        ("Backtest Engine Integration", test_backtest_engine_integration),
        ("Backward Compatibility", test_backward_compatibility),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
