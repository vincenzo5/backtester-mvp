"""
Gap filling service runner.

This service handles gap filling as a separate maintenance job,
running weekly or monthly to fill gaps in cached data.
"""

import logging
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from data.cache_manager import load_manifest, get_manifest_entry
from data.gap_filler import fill_all_gaps
from data.validator import detect_gaps
# Import analyze_all_gaps from local module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.analyze_gaps import analyze_all_gaps

logger = logging.getLogger(__name__)


def load_exchange_metadata() -> Dict[str, Any]:
    """Load exchange metadata configuration."""
    metadata_path = Path('config/exchange_metadata.yaml')
    if not metadata_path.exists():
        raise FileNotFoundError(f"Exchange metadata not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        return yaml.safe_load(f)


def run_gap_filling(priority: str = 'largest', max_gaps: Optional[int] = None) -> Dict[str, Any]:
    """
    Run gap filling for all datasets with gaps.
    
    Args:
        priority: Priority order ('largest' for largest gaps first, 'lowest_coverage' for lowest coverage first)
        max_gaps: Maximum number of gaps to fill (None for all)
    
    Returns:
        Summary dictionary with results
    """
    logger.info("=" * 80)
    logger.info("Gap Filling Service Started")
    logger.info("=" * 80)
    
    # Analyze all gaps
    logger.info("Analyzing gaps across all datasets...")
    all_gaps = analyze_all_gaps()
    
    if not all_gaps:
        logger.info("No gaps found - all datasets are complete!")
        return {
            'status': 'no_gaps',
            'gaps_found': 0,
            'datasets_processed': 0,
            'gaps_filled': 0,
            'total_candles_added': 0
        }
    
    logger.info(f"Found {len(all_gaps)} gap(s) across all datasets")
    
    # Load exchange metadata
    try:
        metadata = load_exchange_metadata()
        exchanges = metadata.get('exchanges', ['coinbase', 'binance', 'kraken'])
    except Exception:
        exchanges = ['coinbase', 'binance', 'kraken']
        logger.warning("Could not load exchange metadata, using defaults")
    
    # Group gaps by dataset
    gaps_by_dataset = {}
    for gap in all_gaps:
        key = (gap['symbol'], gap['timeframe'])
        if key not in gaps_by_dataset:
            gaps_by_dataset[key] = []
        gaps_by_dataset[key].append(gap)
    
    # Sort datasets by priority
    if priority == 'largest':
        # Sort by largest gap in dataset
        dataset_list = sorted(
            gaps_by_dataset.items(),
            key=lambda x: max(g['duration_seconds'] for g in x[1]),
            reverse=True
        )
    elif priority == 'lowest_coverage':
        # Would need coverage calculation - for now, use largest
        dataset_list = sorted(
            gaps_by_dataset.items(),
            key=lambda x: max(g['duration_seconds'] for g in x[1]),
            reverse=True
        )
    else:
        dataset_list = list(gaps_by_dataset.items())
    
    logger.info(f"Processing {len(dataset_list)} dataset(s) with gaps")
    logger.info("-" * 80)
    
    datasets_processed = 0
    total_gaps_filled = 0
    total_candles_added = 0
    failed_datasets = []
    
    gaps_filled_so_far = 0
    
    for i, ((symbol, timeframe), gaps) in enumerate(dataset_list, 1):
        if max_gaps and gaps_filled_so_far >= max_gaps:
            logger.info(f"Reached max_gaps limit ({max_gaps}), stopping")
            break
        
        logger.info(f"[{i}/{len(dataset_list)}] Processing {symbol} {timeframe} ({len(gaps)} gap(s))...")
        
        # Get source exchange from manifest
        manifest_entry = get_manifest_entry(symbol, timeframe)
        source_exchange = manifest_entry.get('source_exchange', 'coinbase') if manifest_entry else 'coinbase'
        
        # Use fallback exchanges (exclude primary)
        fallback_exchanges = [e for e in exchanges if e != source_exchange]
        
        try:
            result = fill_all_gaps(
                symbol, timeframe,
                source_exchange=source_exchange,
                fallback_exchanges=fallback_exchanges
            )
            
            if result['status'] in ['success', 'partial']:
                datasets_processed += 1
                total_gaps_filled += result['gaps_filled']
                total_candles_added += result['total_candles_added']
                gaps_filled_so_far += result['gaps_filled']
                
                logger.info(f"✓ {symbol} {timeframe}: Filled {result['gaps_filled']}/{result['gaps_found']} gaps, "
                          f"added {result['total_candles_added']} candles")
                
                if result['failed_gaps']:
                    logger.warning(f"  {len(result['failed_gaps'])} gap(s) failed to fill")
            else:
                logger.warning(f"✗ {symbol} {timeframe}: Failed to fill gaps")
                failed_datasets.append({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'error': result.get('status', 'unknown')
                })
        
        except Exception as e:
            logger.error(f"✗ Error processing {symbol} {timeframe}: {str(e)}", exc_info=True)
            failed_datasets.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'error': str(e)
            })
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Gap Filling Summary")
    logger.info("=" * 80)
    logger.info(f"Datasets processed: {datasets_processed}")
    logger.info(f"Total gaps filled: {total_gaps_filled}")
    logger.info(f"Total candles added: {total_candles_added:,}")
    if failed_datasets:
        logger.info(f"Failed datasets: {len(failed_datasets)}")
    logger.info("=" * 80)
    
    # Note: Quality reassessment should be triggered after gap filling
    # This can be done via scheduler or manually
    
    return {
        'status': 'success',
        'gaps_found': len(all_gaps),
        'datasets_processed': datasets_processed,
        'gaps_filled': total_gaps_filled,
        'total_candles_added': total_candles_added,
        'failed_datasets': failed_datasets
    }


def main():
    """Main entry point."""
    import sys
    
    # Setup logging
    LOG_DIR = Path('logs')
    LOG_DIR.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_DIR / 'gap_filling.log'),
            logging.StreamHandler()
        ]
    )
    
    # Parse command line arguments
    priority = 'largest'
    max_gaps = None
    
    if len(sys.argv) > 1:
        if '--priority' in sys.argv:
            idx = sys.argv.index('--priority')
            if idx + 1 < len(sys.argv):
                priority = sys.argv[idx + 1]
        if '--max-gaps' in sys.argv:
            idx = sys.argv.index('--max-gaps')
            if idx + 1 < len(sys.argv):
                max_gaps = int(sys.argv[idx + 1])
    
    run_gap_filling(priority=priority, max_gaps=max_gaps)


if __name__ == '__main__':
    main()

