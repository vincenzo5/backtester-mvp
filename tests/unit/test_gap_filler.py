"""
Tests for gap filling functionality.
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtester.data.gap_filler import fill_gap, fill_all_gaps
from backtester.data.cache_manager import write_cache, read_cache, CACHE_DIR, MANIFEST_FILE
from backtester.data.validator import detect_gaps


class TestGapFilling(unittest.TestCase):
    """Test gap filling functions."""
    
    def setUp(self):
        """Set up test cache."""
        self.temp_dir = tempfile.mkdtemp()
        test_cache_dir = Path(self.temp_dir) / 'cache'
        test_cache_dir.mkdir(parents=True)
        
        # Temporarily modify cache path
        from backtester.data import cache_manager as cm_module
        self.original_cache = cm_module.CACHE_DIR
        self.original_manifest = cm_module.MANIFEST_FILE
        cm_module.CACHE_DIR = test_cache_dir
        cm_module.MANIFEST_FILE = test_cache_dir / '.cache_manifest.json'
    
    def tearDown(self):
        """Clean up test cache."""
        shutil.rmtree(self.temp_dir)
        
        # Restore original cache path
        from backtester.data import cache_manager as cm_module
        cm_module.CACHE_DIR = self.original_cache
        cm_module.MANIFEST_FILE = self.original_manifest
    
    def test_fill_gap_invalid_range(self):
        """Test gap filling with invalid date range."""
        # Create data with a gap
        dates1 = pd.date_range(start='2025-01-01', periods=10, freq='1h', tz='UTC')
        dates2 = pd.date_range(start='2025-01-02', periods=10, freq='1h', tz='UTC')  # Gap!
        dates = dates1.union(dates2).sort_values()
        
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, len(dates)),
            'high': np.random.uniform(200, 300, len(dates)),
            'low': np.random.uniform(50, 100, len(dates)),
            'close': np.random.uniform(100, 200, len(dates)),
            'volume': np.random.uniform(1000, 10000, len(dates))
        }, index=dates)
        
        # Fix OHLCV
        for i in range(len(df)):
            high = max(df.iloc[i]['open'], df.iloc[i]['close'])
            low = min(df.iloc[i]['open'], df.iloc[i]['close'])
            df.iloc[i]['high'] = max(high, df.iloc[i]['high'])
            df.iloc[i]['low'] = min(low, df.iloc[i]['low'])
        
        write_cache('BTC/USD', '1h', df, source_exchange='coinbase')
        
        # Try to fill gap - will fail without actual exchange, but tests structure
        gap_start = pd.to_datetime('2025-01-01 10:00:00', utc=True)
        gap_end = pd.to_datetime('2025-01-01 14:00:00', utc=True)
        
        with patch('backtester.data.gap_filler.fetch_historical') as mock_fetch:
            mock_fetch.return_value = (pd.DataFrame(), 0)
            
            result = fill_gap('BTC/USD', '1h', gap_start, gap_end, 'coinbase')
            
            # Should attempt to fetch
            self.assertIsNotNone(result)
            mock_fetch.assert_called_once()
    
    def test_fill_all_gaps_detection(self):
        """Test that fill_all_gaps correctly detects gaps."""
        # Create data with gaps
        dates = pd.date_range(start='2025-01-01', periods=50, freq='1h', tz='UTC')
        # Remove some dates to create gaps
        dates_with_gaps = dates.drop(dates[::10])
        
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, len(dates_with_gaps)),
            'high': np.random.uniform(200, 300, len(dates_with_gaps)),
            'low': np.random.uniform(50, 100, len(dates_with_gaps)),
            'close': np.random.uniform(100, 200, len(dates_with_gaps)),
            'volume': np.random.uniform(1000, 10000, len(dates_with_gaps))
        }, index=dates_with_gaps)
        
        # Fix OHLCV
        for i in range(len(df)):
            high = max(df.iloc[i]['open'], df.iloc[i]['close'])
            low = min(df.iloc[i]['open'], df.iloc[i]['close'])
            df.iloc[i]['high'] = max(high, df.iloc[i]['high'])
            df.iloc[i]['low'] = min(low, df.iloc[i]['low'])
        
        write_cache('BTC/USD', '1h', df, source_exchange='coinbase')
        
        # Detect gaps (should find gaps)
        gaps = detect_gaps(df, '1h')
        self.assertGreater(len(gaps), 0)
        
        # Test fill_all_gaps structure (without actual fetching)
        with patch('backtester.data.gap_filler.fill_gap') as mock_fill:
            mock_fill.return_value = {
                'status': 'no_data',
                'candles_added': 0,
                'error': 'Test error'
            }
            
            result = fill_all_gaps('BTC/USD', '1h', 'coinbase')
            
            # Should detect gaps
            self.assertGreater(result['gaps_found'], 0)


if __name__ == '__main__':
    unittest.main()

