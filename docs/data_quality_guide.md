# Data Quality System - Quick Run Guide

## Overview

The data quality system automatically scores and grades cached OHLCV data, and can automatically fix gaps in your data. This guide shows you how to manually trigger quality assessment and gap filling.

## Quick Start

### Check Data Quality

```bash
# Quick assessment (datasets updated today only)
python3 scripts/assess_all_data_quality.py

# Full assessment (all datasets + liveliness checks)
python3 scripts/assess_all_data_quality.py --full
```

**Output:**
- Console shows grades (A-F) and composite scores for each dataset
- Detailed results logged to `logs/quality_assessment.log`
- Quality scores saved to `data/quality_metadata.json`

### Analyze Gaps

```bash
# View gaps report in terminal
python3 scripts/analyze_gaps.py

# Save to file
python3 scripts/analyze_gaps.py --output gaps_report.json
python3 scripts/analyze_gaps.py --output gaps_report.csv
```

**Output:**
- Lists all gaps across all datasets
- Prioritized by size (largest gaps first)
- Shows missing candle counts, duration, and date ranges

### Fill Gaps Automatically

```bash
# Fill all gaps (prioritizes largest first)
python3 scripts/fill_all_gaps.py

# Fill only top N gaps
python3 scripts/fill_all_gaps.py --max-gaps 10

# Use different priority strategy
python3 scripts/fill_all_gaps.py --priority lowest_coverage
```

**Output:**
- Fetches missing data from exchanges
- Updates cache files automatically
- Logs progress to `logs/gap_filling.log`

## Typical Workflow

### 1. Assess Current Quality
```bash
python3 scripts/assess_all_data_quality.py --full
```

Review the output to see:
- Overall grade distribution (how many A/B/C/D/F datasets)
- Markets with quality issues
- Markets that may be delisted

### 2. Check for Gaps
```bash
python3 scripts/analyze_gaps.py
```

This shows:
- Total number of gaps
- Largest gaps (priority for fixing)
- Missing candle counts

### 3. Fix Gaps
```bash
# Fill all gaps (may take a while if many gaps exist)
python3 scripts/fill_all_gaps.py

# Or fill in smaller batches
python3 scripts/fill_all_gaps.py --max-gaps 50
```

### 4. Re-assess After Fixes
```bash
python3 scripts/assess_all_data_quality.py --full
```

Verify that:
- Coverage scores improved
- Gap scores improved
- Overall grades improved

## Understanding Quality Scores

### Grades
- **A (90-100)**: Excellent - Reliable for backtesting
- **B (80-89)**: Good - Minor issues, generally reliable
- **C (70-79)**: Acceptable - Some issues, use with caution
- **D (60-69)**: Poor - Significant issues, unreliable
- **F (0-59)**: Unusable - Major problems

### Component Scores
Each dataset gets 7 component scores (all 0-100):
- **Coverage** (30% weight): Percentage of expected candles present
- **Integrity** (25% weight): Valid OHLCV price relationships
- **Gaps** (20% weight): Missing data points
- **Completeness** (15% weight): Coverage of desired date range
- **Consistency** (10% weight): Smooth candle transitions
- **Volume** (5% weight): Reasonable volume data
- **Outliers** (5% weight): Statistical anomalies

### Composite Score
Weighted average of all component scores, converted to grade.

## What Gets Fixed Automatically

✅ **Automatically Fixed:**
- **Gaps**: Missing candles are fetched and filled
- **Duplicates**: Duplicate timestamps are removed

❌ **Not Fixed Automatically** (only detected):
- Integrity issues (invalid OHLCV relationships)
- Outliers (statistical anomalies)
- Volume problems (zero/negative volume)
- Consistency issues (cross-candle transitions)
- Missing values (NaN)

## Viewing Quality Data

### Check Specific Dataset Quality

```python
from data.quality_metadata import load_quality_metadata_entry

metadata = load_quality_metadata_entry('BTC/USD', '1h')
print(f"Grade: {metadata['quality_scores']['grade']}")
print(f"Composite: {metadata['quality_scores']['composite']}")
print(f"Coverage: {metadata['quality_scores']['coverage']}")
```

### Check Manifest (Quick Lookup)

```python
from data.cache_manager import get_manifest_entry

entry = get_manifest_entry('BTC/USD', '1h')
print(f"Grade: {entry.get('quality_grade', 'Not Assessed')}")
print(f"Market Live: {entry.get('market_live', None)}")
```

## Automatic Operation

The system also runs automatically via the scheduler:

- **Daily Updates**: Fetches new data, checks quality (if enabled)
- **Weekly Full Assessment**: Sunday 2 AM UTC - assesses all datasets
- **Weekly Gap Filling**: Saturday 3 AM UTC - fills gaps automatically

See `config/config.yaml` for scheduling configuration.

## Troubleshooting

### Low Quality Scores
1. Check component scores to identify which area is problematic
2. For gaps: Run gap filling to improve
3. For integrity: Review the data - may indicate bad source data
4. For outliers: Consider if data is legitimate (crypto can have spikes)

### Gap Filling Not Working
- Check exchange API limits
- Verify market still exists on exchange
- Check logs: `logs/gap_filling.log`

### No Quality Scores
- Run assessment: `python3 scripts/assess_all_data_quality.py --full`
- Check that data exists in cache
- Verify `data/quality_metadata.json` is being written

## File Locations

- **Quality Metadata**: `data/quality_metadata.json` (detailed scores)
- **Cache Manifest**: `data/cache/.cache_manifest.json` (lean info)
- **Assessment Logs**: `logs/quality_assessment.log`
- **Gap Filling Logs**: `logs/gap_filling.log`

## Command Reference

| Task | Command |
|------|---------|
| Assess (quick) | `python3 scripts/assess_all_data_quality.py` |
| Assess (full) | `python3 scripts/assess_all_data_quality.py --full` |
| Analyze gaps | `python3 scripts/analyze_gaps.py` |
| Fill gaps | `python3 scripts/fill_all_gaps.py` |
| Fill limited | `python3 scripts/fill_all_gaps.py --max-gaps 10` |

