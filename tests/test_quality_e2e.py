"""
End-to-end integration tests for the complete data quality system.

Tests the full pipeline from data caching to quality assessment.
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.cache_manager import write_cache, read_cache, get_manifest_entry
from data.quality_scorer import assess_data_quality
from data.quality_metadata import (
    save_quality_metadata_entry, load_quality_metadata_entry,
    load_all_quality_metadata
)
from data.validator import detect_gaps, validate_ohlcv_integrity
from services.quality_runner import assess_dataset_quality


class TestQualitySystemE2E(unittest.TestCase):
    """End-to-end tests for quality system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        test_cache_dir = Path(self.temp_dir) / 'cache'
        test_cache_dir.mkdir(parents=True)
        
        # Temporarily modify paths
        import data.cache_manager as cm_module
        self.original_cache = cm_module.CACHE_DIR
        self.original_manifest = cm_module.MANIFEST_FILE
        cm_module.CACHE_DIR = test_cache_dir
        cm_module.MANIFEST_FILE = test_cache_dir / '.cache_manifest.json'
        
        # Modify quality metadata path
        import data.quality_metadata as qm_module
        self.original_quality_file = qm_module.QUALITY_METADATA_FILE
        qm_module.QUALITY_METADATA_FILE = Path(self.temp_dir) / 'quality_metadata.json'
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
        
        # Restore original paths
        import data.cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache
        cm_module.MANIFEST_FILE = self.original_manifest
        
        import data.quality_metadata as qm_module
        qm_module.QUALITY_METADATA_FILE = self.original_quality_file
    
    def test_full_quality_pipeline(self):
        """Test complete quality assessment pipeline."""
        # Create realistic data
        dates = pd.date_range(
            start='2025-01-01 00:00:00',
            end='2025-01-31 23:00:00',
            freq='1h',
            tz='UTC'
        )
        
        # Create good quality data
        np.random.seed(42)  # For reproducibility
        base_price = 100
        prices = []
        for i in range(len(dates)):
            if i == 0:
                price = base_price
            else:
                # Random walk with small increments
                price = prices[-1] * (1 + np.random.uniform(-0.02, 0.02))
            prices.append(price)
        
        df = pd.DataFrame({
            'open': [p * 0.999 for p in prices],
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': prices,
            'volume': np.random.uniform(1000, 10000, len(dates))
        }, index=dates)
        
        # Write to cache
        write_cache('BTC/USD', '1h', df, source_exchange='coinbase')
        
        # Verify cache
        cached_df = read_cache('BTC/USD', '1h')
        self.assertFalse(cached_df.empty)
        self.assertEqual(len(cached_df), len(df))
        
        # Run quality assessment via service (which saves metadata)
        from services.quality_runner import assess_dataset_quality
        
        result = assess_dataset_quality(
            'BTC/USD', '1h',
            perform_liveliness_check=False
        )
        
        # Verify assessment results
        self.assertEqual(result['status'], 'success')
        self.assertIn('composite_score', result)
        self.assertIn('grade', result)
        self.assertIn('component_scores', result)
        
        # Composite should be reasonable
        self.assertGreater(result['composite_score'], 50)  # At least some data quality
        self.assertLessEqual(result['composite_score'], 100)
        
        # Grade should be valid
        self.assertIn(result['grade'], ['A', 'B', 'C', 'D', 'F'])
        
        # Verify quality metadata was saved
        metadata = load_quality_metadata_entry('BTC/USD', '1h')
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['symbol'], 'BTC/USD')
        self.assertEqual(metadata['timeframe'], '1h')
        self.assertIn('quality_scores', metadata)
        self.assertEqual(metadata['quality_scores']['grade'], result['grade'])
        self.assertEqual(metadata['quality_scores']['composite'], result['composite_score'])
        
        # Verify manifest was updated (if quality was saved)
        manifest_entry = get_manifest_entry('BTC/USD', '1h')
        self.assertIsNotNone(manifest_entry)
        # Manifest should have basic info
        self.assertIn('symbol', manifest_entry)
        self.assertIn('timeframe', manifest_entry)
    
    def test_quality_assessment_service_integration(self):
        """Test quality assessment service integration."""
        # Create test data
        dates = pd.date_range(
            start='2025-01-01',
            end='2025-01-15',
            freq='1h',
            tz='UTC'
        )
        
        np.random.seed(42)
        base_price = 100
        prices = [base_price]
        for i in range(1, len(dates)):
            prices.append(prices[-1] * (1 + np.random.uniform(-0.01, 0.01)))
        
        df = pd.DataFrame({
            'open': [p * 0.998 for p in prices],
            'high': [p * 1.015 for p in prices],
            'low': [p * 0.995 for p in prices],
            'close': prices,
            'volume': np.random.uniform(1000, 5000, len(dates))
        }, index=dates)
        
        write_cache('ETH/USD', '1h', df, source_exchange='coinbase')
        
        # Run assessment via service
        result = assess_dataset_quality(
            'ETH/USD', '1h',
            perform_liveliness_check=False  # Skip external checks
        )
        
        # Verify service results
        self.assertEqual(result['status'], 'success')
        self.assertIn('grade', result)
        self.assertIn('composite_score', result)
        
        # Verify metadata was saved
        metadata = load_quality_metadata_entry('ETH/USD', '1h')
        self.assertIsNotNone(metadata)
    
    def test_data_with_gaps(self):
        """Test quality assessment with gaps in data."""
        # Create data with intentional gaps
        dates = pd.date_range(
            start='2025-01-01',
            end='2025-01-10',
            freq='1h',
            tz='UTC'
        )
        
        # Remove every 5th date to create gaps
        dates_with_gaps = dates.drop(dates[::5])
        
        np.random.seed(42)
        prices = [100 + i * 0.1 for i in range(len(dates_with_gaps))]
        
        df = pd.DataFrame({
            'open': [p * 0.999 for p in prices],
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': prices,
            'volume': np.random.uniform(1000, 5000, len(dates_with_gaps))
        }, index=dates_with_gaps)
        
        write_cache('GAP/USD', '1h', df, source_exchange='coinbase')
        
        # Verify gaps detected
        gaps = detect_gaps(df, '1h')
        self.assertGreater(len(gaps), 0)
        
        # Run quality assessment via service
        from services.quality_runner import assess_dataset_quality
        
        result = assess_dataset_quality(
            'GAP/USD', '1h',
            perform_liveliness_check=False
        )
        
        # Should still assess, but with lower gap score
        self.assertEqual(result['status'], 'success')
        self.assertIn('composite_score', result)
        
        # Gaps component should be lower
        gap_score = result['component_scores'].get('gaps', 100)
        self.assertLess(gap_score, 100)  # Gaps should reduce score
    
    def test_empty_data_handling(self):
        """Test handling of empty or missing data."""
        # Try to assess non-existent data
        result = assess_data_quality('NONEXISTENT/USD', '1h')
        
        # Should handle gracefully
        self.assertEqual(result['status'], 'no_data')
        self.assertEqual(result.get('composite', 0), 0)
        self.assertEqual(result.get('grade', 'F'), 'F')
    
    def test_all_quality_metadata_loading(self):
        """Test loading all quality metadata."""
        # Create multiple datasets
        for symbol in ['BTC/USD', 'ETH/USD']:
            dates = pd.date_range('2025-01-01', periods=100, freq='1h', tz='UTC')
            df = pd.DataFrame({
                'open': np.random.uniform(100, 200, 100),
                'high': np.random.uniform(200, 300, 100),
                'low': np.random.uniform(50, 100, 100),
                'close': np.random.uniform(100, 200, 100),
                'volume': np.random.uniform(1000, 10000, 100)
            }, index=dates)
            
            # Fix OHLCV
            for i in range(len(df)):
                high = max(df.iloc[i]['open'], df.iloc[i]['close'])
                low = min(df.iloc[i]['open'], df.iloc[i]['close'])
                df.iloc[i]['high'] = max(high, df.iloc[i]['high'])
                df.iloc[i]['low'] = min(low, df.iloc[i]['low'])
            
            write_cache(symbol, '1h', df)
            
            # Assess quality via service (saves metadata)
            from services.quality_runner import assess_dataset_quality
            assess_dataset_quality(symbol, '1h', perform_liveliness_check=False)
        
        # Load all metadata
        all_metadata = load_all_quality_metadata()
        
        # Should have entries
        self.assertGreater(len(all_metadata), 0)
        
        # Should have our test symbols
        self.assertIn('BTC/USD_1h', all_metadata)
        self.assertIn('ETH/USD_1h', all_metadata)


if __name__ == '__main__':
    unittest.main()

