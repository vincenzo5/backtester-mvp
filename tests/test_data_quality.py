"""
Tests for data quality system.

Tests validation functions, quality scoring, and quality assessment pipeline.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import shutil
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtester.data.validator import (
    validate_ohlcv_integrity, validate_volume, detect_outliers,
    validate_cross_candle_consistency, validate_missing_values,
    validate_chronological_order, detect_gaps
)
from backtester.data.quality_scorer import (
    calculate_component_scores, calculate_composite_score,
    assess_data_quality
)
from backtester.data.cache_manager import write_cache, read_cache, update_manifest, load_manifest
from backtester.data.quality_metadata import (
    save_quality_metadata_entry, load_quality_metadata_entry,
    load_all_quality_metadata, delete_quality_metadata_entry
)


class TestValidationFunctions(unittest.TestCase):
    """Test validation functions."""
    
    def setUp(self):
        """Create sample data for testing."""
        dates = pd.date_range(start='2025-01-01', periods=100, freq='1h', tz='UTC')
        self.good_df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(200, 300, 100),
            'low': np.random.uniform(50, 100, 100),
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.uniform(1000, 10000, 100)
        }, index=dates)
        
        # Fix OHLCV relationships
        for i in range(len(self.good_df)):
            high = max(self.good_df.iloc[i]['open'], self.good_df.iloc[i]['close'])
            low = min(self.good_df.iloc[i]['open'], self.good_df.iloc[i]['close'])
            self.good_df.iloc[i]['high'] = max(high, self.good_df.iloc[i]['high'])
            self.good_df.iloc[i]['low'] = min(low, self.good_df.iloc[i]['low'])
    
    def test_validate_ohlcv_integrity_good_data(self):
        """Test integrity validation with good data."""
        result = validate_ohlcv_integrity(self.good_df)
        self.assertEqual(result['valid_count'], 100)
        self.assertEqual(result['invalid_count'], 0)
        self.assertEqual(len(result['issues']), 0)
    
    def test_validate_ohlcv_integrity_bad_data(self):
        """Test integrity validation with bad data."""
        bad_df = self.good_df.copy()
        bad_df.iloc[0]['high'] = 50  # High < low (invalid)
        bad_df.iloc[1]['open'] = -10  # Negative price
        
        result = validate_ohlcv_integrity(bad_df)
        self.assertGreater(result['invalid_count'], 0)
        self.assertGreater(len(result['issues']), 0)
    
    def test_detect_outliers(self):
        """Test outlier detection."""
        df_with_outliers = self.good_df.copy()
        # Add extreme outlier
        df_with_outliers.iloc[50]['close'] = 999999
        
        outliers = detect_outliers(df_with_outliers, method='iqr', multiplier=1.5)
        self.assertIn(df_with_outliers.index[50], outliers)
    
    def test_validate_volume(self):
        """Test volume validation."""
        df_with_zero_volume = self.good_df.copy()
        df_with_zero_volume.iloc[0]['volume'] = 0
        
        result = validate_volume(df_with_zero_volume)
        self.assertGreater(result['zero_volume_count'], 0)
    
    def test_validate_cross_candle_consistency(self):
        """Test cross-candle consistency validation."""
        # Create data with consistent transitions
        result = validate_cross_candle_consistency(self.good_df, tolerance=0.01)
        self.assertGreater(result['consistent_count'], 0)
        self.assertIsInstance(result['total_transitions'], int)
    
    def test_validate_chronological_order(self):
        """Test chronological order validation."""
        # Good data should be in order
        self.assertTrue(validate_chronological_order(self.good_df))
        
        # Shuffled data should fail
        shuffled_df = self.good_df.sample(frac=1)
        self.assertFalse(validate_chronological_order(shuffled_df))
    
    def test_detect_gaps(self):
        """Test gap detection."""
        # Create data with gaps
        dates_with_gaps = pd.date_range(start='2025-01-01', periods=50, freq='1h', tz='UTC')
        # Remove every 10th date to create gaps
        dates_with_gaps = dates_with_gaps.drop(dates_with_gaps[::10])
        df_with_gaps = pd.DataFrame({
            'open': np.random.uniform(100, 200, len(dates_with_gaps)),
            'high': np.random.uniform(200, 300, len(dates_with_gaps)),
            'low': np.random.uniform(50, 100, len(dates_with_gaps)),
            'close': np.random.uniform(100, 200, len(dates_with_gaps)),
            'volume': np.random.uniform(1000, 10000, len(dates_with_gaps))
        }, index=dates_with_gaps)
        
        gaps = detect_gaps(df_with_gaps, '1h')
        self.assertGreater(len(gaps), 0)


class TestQualityScoring(unittest.TestCase):
    """Test quality scoring functions."""
    
    def setUp(self):
        """Create sample data for testing."""
        dates = pd.date_range(start='2025-01-01', end='2025-01-31', freq='1h', tz='UTC')
        self.df = pd.DataFrame({
            'open': np.random.uniform(100, 200, len(dates)),
            'high': np.random.uniform(200, 300, len(dates)),
            'low': np.random.uniform(50, 100, len(dates)),
            'close': np.random.uniform(100, 200, len(dates)),
            'volume': np.random.uniform(1000, 10000, len(dates))
        }, index=dates)
        
        # Fix OHLCV relationships
        for i in range(len(self.df)):
            high = max(self.df.iloc[i]['open'], self.df.iloc[i]['close'])
            low = min(self.df.iloc[i]['open'], self.df.iloc[i]['close'])
            self.df.iloc[i]['high'] = max(high, self.df.iloc[i]['high'])
            self.df.iloc[i]['low'] = min(low, self.df.iloc[i]['low'])
    
    def test_calculate_component_scores(self):
        """Test component score calculation."""
        start_date = pd.to_datetime('2025-01-01')
        end_date = pd.to_datetime('2025-01-31')
        
        scores = calculate_component_scores(
            self.df, '1h', start_date, end_date
        )
        
        # All scores should be between 0 and 100
        for component, score in scores.items():
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
    
    def test_calculate_composite_score(self):
        """Test composite score calculation."""
        component_scores = {
            'coverage': 95.0,
            'gaps': 98.0,
            'integrity': 100.0,
            'volume': 97.0,
            'consistency': 96.0,
            'outliers': 99.0,
            'completeness': 94.0
        }
        
        result = calculate_composite_score(component_scores)
        
        self.assertIn('composite', result)
        self.assertIn('grade', result)
        self.assertGreaterEqual(result['composite'], 0)
        self.assertLessEqual(result['composite'], 100)
        self.assertIn(result['grade'], ['A', 'B', 'C', 'D', 'F'])


class TestQualityMetadata(unittest.TestCase):
    """Test quality metadata storage."""
    
    def setUp(self):
        """Set up temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_path = Path('data/quality_metadata.json')
        # Backup if exists
        if self.original_path.exists():
            self.backup = self.original_path.read_text()
        else:
            self.backup = None
        
        # Modify Path to use temp dir (for testing only)
        import data.quality_metadata as qm_module
        self.original_quality_file = qm_module.QUALITY_METADATA_FILE
        qm_module.QUALITY_METADATA_FILE = Path(self.temp_dir) / 'quality_metadata.json'
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
        import data.quality_metadata as qm_module
        qm_module.QUALITY_METADATA_FILE = self.original_quality_file
        
        # Restore backup
        if self.backup:
            self.original_path.write_text(self.backup)
        elif self.original_path.exists():
            self.original_path.unlink()
    
    def test_save_and_load_quality_metadata(self):
        """Test saving and loading quality metadata."""
        scores = {
            'coverage': 95.0,
            'gaps': 98.0,
            'integrity': 100.0,
            'composite': 97.5,
            'grade': 'A'
        }
        
        save_quality_metadata_entry('BTC/USD', '1h', scores)
        
        loaded = load_quality_metadata_entry('BTC/USD', '1h')
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['symbol'], 'BTC/USD')
        self.assertEqual(loaded['timeframe'], '1h')
        self.assertEqual(loaded['quality_scores']['grade'], 'A')


class TestEndToEndQualityAssessment(unittest.TestCase):
    """End-to-end tests for quality assessment."""
    
    def setUp(self):
        """Set up test cache."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = Path('data')
        
        # Create test cache directory
        test_cache_dir = Path(self.temp_dir) / 'cache'
        test_cache_dir.mkdir(parents=True)
        
        # Temporarily modify cache path (for testing)
        import data.cache_manager as cm_module
        self.original_cache = cm_module.CACHE_DIR
        self.original_manifest = cm_module.MANIFEST_FILE
        cm_module.CACHE_DIR = test_cache_dir
        cm_module.MANIFEST_FILE = test_cache_dir / '.cache_manifest.json'
    
    def tearDown(self):
        """Clean up test cache."""
        shutil.rmtree(self.temp_dir)
        
        # Restore original cache path
        import data.cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache
        cm_module.MANIFEST_FILE = self.original_manifest
    
    def test_full_quality_assessment_pipeline(self):
        """Test complete quality assessment pipeline."""
        # Create sample data
        dates = pd.date_range(start='2025-01-01', end='2025-01-10', freq='1h', tz='UTC')
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, len(dates)),
            'high': np.random.uniform(200, 300, len(dates)),
            'low': np.random.uniform(50, 100, len(dates)),
            'close': np.random.uniform(100, 200, len(dates)),
            'volume': np.random.uniform(1000, 10000, len(dates))
        }, index=dates)
        
        # Fix OHLCV relationships
        for i in range(len(df)):
            high = max(df.iloc[i]['open'], df.iloc[i]['close'])
            low = min(df.iloc[i]['open'], df.iloc[i]['close'])
            df.iloc[i]['high'] = max(high, df.iloc[i]['high'])
            df.iloc[i]['low'] = min(low, df.iloc[i]['low'])
        
        # Write to cache
        write_cache('BTC/USD', '1h', df, source_exchange='coinbase')
        
        # Run quality assessment
        result = assess_data_quality('BTC/USD', '1h')
        
        # Verify results
        self.assertEqual(result['status'], 'assessed')
        self.assertIn('composite', result)
        self.assertIn('grade', result)
        self.assertGreater(result['composite'], 0)
        
        # Verify manifest was updated
        from data.cache_manager import get_manifest_entry
        manifest_entry = get_manifest_entry('BTC/USD', '1h')
        self.assertIsNotNone(manifest_entry)
        if 'quality_grade' in manifest_entry:
            self.assertIn(manifest_entry['quality_grade'], ['A', 'B', 'C', 'D', 'F', 'Not Assessed'])


if __name__ == '__main__':
    unittest.main()

