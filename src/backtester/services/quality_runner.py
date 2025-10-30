"""
Quality assessment service.

This service handles quality scoring for cached datasets,
running either incremental (changed datasets) or full assessments.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import pandas as pd

from backtester.data.cache_manager import load_manifest, read_cache, update_manifest, get_manifest_entry
from backtester.data.quality_scorer import assess_data_quality, load_quality_weights, load_quality_thresholds
from backtester.data.quality_metadata import save_quality_metadata_entry, load_quality_metadata_entry
from backtester.data.market_liveliness import check_all_exchanges, is_liveliness_stale
from backtester.data.validator import detect_gaps, validate_ohlcv_integrity, detect_outliers, validate_cross_candle_consistency
from backtester.config import ConfigManager

logger = logging.getLogger(__name__)


def load_exchange_metadata() -> Dict[str, Any]:
    """Load exchange metadata configuration."""
    config = ConfigManager()
    return config.get_exchange_metadata()


def get_datasets_updated_today() -> List[Tuple[str, str]]:
    """
    Get list of datasets that were updated today.
    
    Returns:
        List of (symbol, timeframe) tuples
    """
    manifest = load_manifest()
    today = datetime.utcnow().date()
    updated_today = []
    
    for key, entry in manifest.items():
        last_updated = entry.get('last_updated')
        if last_updated:
            try:
                updated_date = pd.to_datetime(last_updated).date()
                if updated_date == today:
                    updated_today.append((entry['symbol'], entry['timeframe']))
            except Exception:
                continue
    
    return updated_today


def assess_dataset_quality(symbol: str, timeframe: str, 
                          perform_liveliness_check: bool = False,
                          exchanges: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Assess quality for a single dataset.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USD')
        timeframe: Data granularity (e.g., '1h', '1d')
        perform_liveliness_check: Whether to perform full liveliness check
        exchanges: List of exchanges to check (loads from config if None)
    
    Returns:
        Dictionary with assessment results
    """
    # Load data
    df = read_cache(symbol, timeframe)
    
    if df.empty:
        return {
            'status': 'no_data',
            'symbol': symbol,
            'timeframe': timeframe,
            'error': 'No cached data available'
        }
    
    # Get dates from manifest
    manifest_entry = get_manifest_entry(symbol, timeframe)
    start_date = None
    end_date = None
    
    if manifest_entry:
        if manifest_entry.get('first_date'):
            start_date = pd.to_datetime(manifest_entry['first_date'])
        if manifest_entry.get('last_date'):
            end_date = pd.to_datetime(manifest_entry['last_date'])
    
    # Perform quality assessment
    try:
        assessment = assess_data_quality(symbol, timeframe, start_date, end_date)
        
        if assessment.get('status') != 'assessed':
            return {
                'status': 'failed',
                'symbol': symbol,
                'timeframe': timeframe,
                'error': assessment.get('status', 'Unknown error')
            }
        
        component_scores = assessment['component_scores']
        composite_score = assessment['composite']
        grade = assessment['grade']
        
        # Get detailed validation results
        gaps = detect_gaps(df, timeframe)
        integrity_result = validate_ohlcv_integrity(df)
        outlier_indices = detect_outliers(df, method='iqr', multiplier=1.5)
        consistency_result = validate_cross_candle_consistency(df, tolerance=0.01)
        
        # Convert gaps to JSON-serializable format (timestamps to strings)
        gaps_serializable = []
        for gap in gaps[:10]:  # Store first 10 gaps
            gaps_serializable.append({
                'start': gap['start'] if isinstance(gap['start'], str) else gap['start'].isoformat(),
                'end': gap['end'] if isinstance(gap['end'], str) else gap['end'].isoformat(),
                'expected_candles': gap['expected_candles'],
                'missing_candles': gap['missing_candles'],
                'duration_seconds': gap['duration_seconds']
            })
        
        # Convert outlier indices to strings if they're timestamps
        outlier_sample = []
        for idx in (outlier_indices[:10] if outlier_indices else []):
            if isinstance(idx, pd.Timestamp):
                outlier_sample.append(idx.isoformat())
            else:
                outlier_sample.append(str(idx))
        
        assessment_details = {
            'gaps': gaps_serializable,
            'gap_count': len(gaps),
            'outliers': len(outlier_indices),
            'outlier_sample': outlier_sample,
            'integrity_issues': integrity_result.get('issues', [])[:10],  # Store sample
            'consistency_issues': consistency_result.get('inconsistent_count', 0)
        }
        
        # Perform liveliness check if requested
        market_status = None
        if perform_liveliness_check:
            if exchanges is None:
                metadata = load_exchange_metadata()
                exchanges = metadata.get('exchanges', ['coinbase', 'binance', 'kraken'])
            
            try:
                market_status = check_all_exchanges(symbol, exchanges, timeframe='1h')
            except Exception as e:
                logger.warning(f"Error checking liveliness for {symbol} {timeframe}: {str(e)}")
                market_status = {
                    'live': None,
                    'exchanges': [],
                    'delisted': None,
                    'verified_date': datetime.utcnow().isoformat() + 'Z',
                    'error': str(e)
                }
        
        # Save detailed quality metadata
        save_quality_metadata_entry(
            symbol, timeframe,
            scores={
                **component_scores,
                'composite': composite_score,
                'grade': grade,
                'status': 'assessed'
            },
            market_status=market_status,
            assessment_details=assessment_details
        )
        
        # Update manifest with lean quality info
        update_manifest(
            symbol, timeframe, df,
            quality_grade=grade,
            quality_assessment_date=assessment.get('assessment_date', datetime.utcnow().isoformat() + 'Z'),
            market_live=market_status.get('live') if market_status else None,
            market_verified_date=market_status.get('verified_date') if market_status else None
        )
        
        return {
            'status': 'success',
            'symbol': symbol,
            'timeframe': timeframe,
            'grade': grade,
            'composite_score': composite_score,
            'component_scores': component_scores,
            'market_live': market_status.get('live') if market_status else None
        }
    
    except Exception as e:
        logger.error(f"Error assessing quality for {symbol} {timeframe}: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'symbol': symbol,
            'timeframe': timeframe,
            'error': str(e)
        }


def run_incremental_assessment() -> Dict[str, Any]:
    """
    Run incremental quality assessment - only assess datasets updated today.
    
    Returns:
        Summary dictionary with results
    """
    logger.info("=" * 80)
    logger.info("Incremental Quality Assessment Started")
    logger.info("=" * 80)
    
    updated_today = get_datasets_updated_today()
    
    if not updated_today:
        logger.info("No datasets updated today - nothing to assess")
        return {
            'status': 'no_updates',
            'assessed': 0,
            'failed': 0
        }
    
    logger.info(f"Found {len(updated_today)} dataset(s) updated today")
    logger.info("-" * 80)
    
    assessed = 0
    failed = 0
    results = []
    
    for symbol, timeframe in updated_today:
        logger.info(f"Assessing {symbol} {timeframe}...")
        
        result = assess_dataset_quality(
            symbol, timeframe,
            perform_liveliness_check=False  # Don't check liveliness in incremental (too expensive)
        )
        
        if result.get('status') == 'success':
            logger.info(f"✓ {symbol} {timeframe}: Grade {result.get('grade', 'N/A')}, "
                       f"Score {result.get('composite_score', 0):.2f}")
            assessed += 1
        else:
            logger.warning(f"✗ {symbol} {timeframe}: {result.get('error', 'Failed')}")
            failed += 1
        
        results.append(result)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Incremental Assessment Summary")
    logger.info("=" * 80)
    logger.info(f"Assessed: {assessed}")
    logger.info(f"Failed: {failed}")
    logger.info("=" * 80)
    
    return {
        'status': 'success',
        'assessed': assessed,
        'failed': failed,
        'results': results
    }


def run_full_assessment() -> Dict[str, Any]:
    """
    Run full quality assessment - assess all cached datasets.
    Includes full liveliness checks.
    
    Returns:
        Summary dictionary with results
    """
    logger.info("=" * 80)
    logger.info("Full Quality Assessment Started")
    logger.info("=" * 80)
    
    manifest = load_manifest()
    
    if not manifest:
        logger.info("No cached datasets found")
        return {
            'status': 'no_data',
            'assessed': 0,
            'failed': 0
        }
    
    # Load exchange list
    try:
        metadata = load_exchange_metadata()
        exchanges = metadata.get('exchanges', ['coinbase', 'binance', 'kraken'])
    except Exception:
        exchanges = ['coinbase', 'binance', 'kraken']
        logger.warning("Could not load exchange metadata, using defaults")
    
    logger.info(f"Assessing {len(manifest)} dataset(s)")
    logger.info(f"Exchange list: {exchanges}")
    logger.info("-" * 80)
    
    assessed = 0
    failed = 0
    results = []
    
    for i, (key, entry) in enumerate(manifest.items(), 1):
        symbol = entry['symbol']
        timeframe = entry['timeframe']
        
        logger.info(f"[{i}/{len(manifest)}] Assessing {symbol} {timeframe}...")
        
        # Perform full check (including liveliness) every 10th dataset to spread load
        check_liveliness = (i % 10 == 0)
        
        result = assess_dataset_quality(
            symbol, timeframe,
            perform_liveliness_check=check_liveliness,
            exchanges=exchanges
        )
        
        if result.get('status') == 'success':
            logger.info(f"✓ {symbol} {timeframe}: Grade {result.get('grade', 'N/A')}, "
                       f"Score {result.get('composite_score', 0):.2f}")
            assessed += 1
        else:
            logger.warning(f"✗ {symbol} {timeframe}: {result.get('error', 'Failed')}")
            failed += 1
        
        results.append(result)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Full Assessment Summary")
    logger.info("=" * 80)
    logger.info(f"Assessed: {assessed}")
    logger.info(f"Failed: {failed}")
    logger.info("=" * 80)
    
    return {
        'status': 'success',
        'assessed': assessed,
        'failed': failed,
        'results': results
    }


def main():
    """Main entry point."""
    import sys
    
    # Setup logging
    LOG_DIR = Path('artifacts/logs')
    LOG_DIR.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_DIR / 'quality_assessment.log'),
            logging.StreamHandler()
        ]
    )
    
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        run_full_assessment()
    else:
        run_incremental_assessment()


if __name__ == '__main__':
    main()

