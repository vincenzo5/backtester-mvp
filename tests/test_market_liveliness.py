"""
Tests for market liveliness detection.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtester.data.market_liveliness import (
    check_market_on_exchange, check_all_exchanges,
    check_market_live, is_liveliness_stale
)


class TestMarketLiveliness(unittest.TestCase):
    """Test market liveliness functions."""
    
    @patch('data.market_liveliness.create_exchange')
    def test_check_market_on_exchange_success(self, mock_create_exchange):
        """Test successful market check."""
        # Mock exchange
        mock_exchange = Mock()
        mock_exchange.id = 'coinbase'
        
        # Mock successful OHLCV fetch
        mock_exchange.fetch_ohlcv.return_value = [
            [1609459200000, 29000, 30000, 28000, 29500, 1000]  # Valid candle
        ]
        
        mock_create_exchange.return_value = mock_exchange
        
        result = check_market_on_exchange(mock_exchange, 'BTC/USD', '1h')
        
        self.assertIsNotNone(result)
        self.assertTrue(result['exists'])
        self.assertEqual(result['exchange_id'], 'coinbase')
    
    @patch('data.market_liveliness.create_exchange')
    def test_check_market_on_exchange_not_found(self, mock_create_exchange):
        """Test market not found."""
        mock_exchange = Mock()
        mock_exchange.fetch_ohlcv.side_effect = Exception('Market not found')
        
        mock_create_exchange.return_value = mock_exchange
        
        result = check_market_on_exchange(mock_exchange, 'INVALID/USD', '1h')
        
        self.assertIsNone(result)
    
    def test_is_liveliness_stale(self):
        """Test staleness check."""
        # Test None (never checked)
        self.assertTrue(is_liveliness_stale(None))
        
        # Test fresh date (within cache period) - use recent date
        from datetime import timedelta
        fresh_dt = datetime.now(timezone.utc) - timedelta(days=15)
        # Format like the code does: isoformat() + 'Z', but need to handle timezone properly
        fresh_date = fresh_dt.replace(tzinfo=None).isoformat() + 'Z'
        self.assertFalse(is_liveliness_stale(fresh_date, cache_days=30))
        
        # Test stale date (outside cache period)
        stale_dt = datetime.now(timezone.utc) - timedelta(days=31)
        stale_date = stale_dt.replace(tzinfo=None).isoformat() + 'Z'
        self.assertTrue(is_liveliness_stale(stale_date, cache_days=30))
    
    @patch('data.market_liveliness.create_exchange')
    def test_check_all_exchanges_success(self, mock_create_exchange):
        """Test checking all exchanges with success."""
        # Mock first exchange has market
        mock_exchange1 = Mock()
        mock_exchange1.id = 'coinbase'
        mock_exchange1.fetch_ohlcv.return_value = [
            [1609459200000, 29000, 30000, 28000, 29500, 1000]
        ]
        
        # Mock second exchange doesn't have market
        mock_exchange2 = Mock()
        mock_exchange2.id = 'binance'
        mock_exchange2.fetch_ohlcv.side_effect = Exception('Market not found')
        
        def create_exchange_side_effect(name, **kwargs):
            if name == 'coinbase':
                return mock_exchange1
            elif name == 'binance':
                return mock_exchange2
            return Mock()
        
        mock_create_exchange.side_effect = create_exchange_side_effect
        
        result = check_all_exchanges('BTC/USD', ['coinbase', 'binance'], '1h')
        
        self.assertTrue(result['live'])
        self.assertIn('coinbase', result['exchanges'])
        self.assertNotIn('binance', result['exchanges'])
        self.assertFalse(result['delisted'])


if __name__ == '__main__':
    unittest.main()

