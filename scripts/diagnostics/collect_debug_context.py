#!/usr/bin/env python3
"""
Collect comprehensive debug context for troubleshooting backtest failures.

Aggregates execution traces, crash reports, and diagnostic information into
a unified Markdown report for analysis.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def read_last_n_lines(file_path: Path, n: int = 100) -> List[str]:
    """
    Efficiently read last N lines from a file.
    
    Args:
        file_path: Path to file
        n: Number of lines to read
        
    Returns:
        List of last N lines
    """
    if not file_path.exists():
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return lines[-n:] if len(lines) > n else lines
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []


def load_jsonl_lines(file_path: Path, n: int = 50) -> List[Dict[str, Any]]:
    """
    Read last N JSONL entries from execution trace.
    
    Args:
        file_path: Path to JSONL file
        n: Number of entries to read
        
    Returns:
        List of parsed JSON objects
    """
    if not file_path.exists():
        return []
    
    entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-n:]:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"Warning: Could not read JSONL file {file_path}: {e}")
    
    return entries


def list_crash_reports(crash_report_dir: Path) -> List[Dict[str, Any]]:
    """
    List crash reports sorted by timestamp (newest first).
    
    Args:
        crash_report_dir: Directory containing crash reports
        
    Returns:
        List of crash report metadata
    """
    if not crash_report_dir.exists():
        return []
    
    reports = []
    for report_file in sorted(crash_report_dir.glob('crash_*.json'), 
                               key=lambda p: p.stat().st_mtime, 
                               reverse=True):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                reports.append({
                    'file': report_file.name,
                    'timestamp': report.get('timestamp'),
                    'trigger_type': report.get('trigger_type'),
                    'severity': report.get('severity'),
                    'report_id': report.get('report_id')
                })
        except Exception:
            continue
    
    return reports[:20]  # Limit to 20 most recent


def call_diagnostic_script(script_name: str, *args) -> Optional[Dict[str, Any]]:
    """
    Call an existing diagnostic script and capture output.
    
    Args:
        script_name: Name of diagnostic script (without .py)
        *args: Arguments to pass to script
        
    Returns:
        Dictionary with script output or None if failed
    """
    scripts_dir = Path(__file__).parent
    script_path = scripts_dir / f"{script_name}.py"
    
    if not script_path.exists():
        return None
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)] + list(args),
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'success': result.returncode == 0
        }
    except Exception as e:
        return {'error': str(e), 'success': False}


def get_system_info() -> Dict[str, Any]:
    """Get system information."""
    info = {}
    
    try:
        import psutil
        info['memory_total_mb'] = psutil.virtual_memory().total / (1024 * 1024)
        info['memory_used_mb'] = psutil.virtual_memory().used / (1024 * 1024)
        info['memory_percent'] = psutil.virtual_memory().percent
        info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        info['cpu_count'] = psutil.cpu_count()
    except ImportError:
        info['psutil_not_available'] = True
    
    try:
        import shutil
        disk_usage = shutil.disk_usage(Path.cwd())
        info['disk_free_gb'] = disk_usage.free / (1024 * 1024 * 1024)
        info['disk_total_gb'] = disk_usage.total / (1024 * 1024 * 1024)
    except Exception:
        pass
    
    return info


def collect_context(output_file: Optional[Path] = None) -> str:
    """
    Collect all debug context and generate Markdown report.
    
    Args:
        output_file: Optional path to write report (default: stdout)
        
    Returns:
        Markdown report as string
    """
    report_lines = []
    
    # Header
    report_lines.append("# Debug Context Report")
    report_lines.append(f"Generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n")
    
    # Try to load config
    debug_config = None
    try:
        from backtester.config import ConfigManager
        config = ConfigManager()
        debug_config = config.get_debug_config()
        
        report_lines.append("## Configuration")
        report_lines.append(f"- Debug Enabled: {debug_config.enabled}")
        report_lines.append(f"- Tracing Enabled: {debug_config.tracing.enabled}")
        report_lines.append(f"- Crash Reports Enabled: {debug_config.crash_reports.enabled}")
        report_lines.append("")
    except Exception as e:
        report_lines.append("## Configuration")
        report_lines.append(f"⚠️ Could not load config: {e}")
        report_lines.append("")
    
    # Execution Trace
    report_lines.append("## Execution Trace (Last 50 Entries)")
    if debug_config:
        trace_file = Path(debug_config.logging.execution_trace_file)
        crash_dir = Path(debug_config.logging.crash_report_dir)
    else:
        trace_file = Path('artifacts/logs/backtest_execution.jsonl')
        crash_dir = Path('artifacts/logs/crash_reports')
    
    entries = []
    if trace_file.exists():
        entries = load_jsonl_lines(trace_file, n=50)
        if entries:
            report_lines.append(f"Found {len(entries)} recent entries\n")
            for entry in entries[-10:]:  # Show last 10
                report_lines.append(f"### {entry.get('event_type', 'unknown')}")
                report_lines.append(f"- Timestamp: {entry.get('timestamp')}")
                report_lines.append(f"- Message: {entry.get('message', 'N/A')}")
                if entry.get('error_type'):
                    report_lines.append(f"- Error: {entry.get('error_type')}: {entry.get('error_message')}")
                report_lines.append("")
        else:
            report_lines.append("No entries found in execution trace.\n")
    else:
        report_lines.append(f"⚠️ Execution trace file not found: {trace_file}\n")
    
    # Crash Reports
    report_lines.append("## Crash Reports")
    
    reports = list_crash_reports(crash_dir)
    if reports:
        report_lines.append(f"Found {len(reports)} crash reports (showing 10 most recent):\n")
        for report in reports[:10]:
            report_lines.append(f"### {report['report_id']}")
            report_lines.append(f"- Trigger: {report['trigger_type']}")
            report_lines.append(f"- Severity: {report['severity']}")
            report_lines.append(f"- Timestamp: {report['timestamp']}")
            report_lines.append(f"- File: {report['file']}")
            report_lines.append("")
    else:
        report_lines.append("No crash reports found.\n")
    
    # System Information
    report_lines.append("## System Information")
    system_info = get_system_info()
    for key, value in system_info.items():
        if isinstance(value, float):
            report_lines.append(f"- {key}: {value:.2f}")
        else:
            report_lines.append(f"- {key}: {value}")
    report_lines.append("")
    
    # Diagnostic Scripts
    report_lines.append("## Diagnostic Scripts")
    
    # Run diagnose_no_trades if available
    no_trades_result = call_diagnostic_script('diagnose_no_trades')
    if no_trades_result:
        report_lines.append("### diagnose_no_trades.py")
        if no_trades_result.get('success'):
            report_lines.append("```")
            report_lines.append(no_trades_result.get('stdout', 'No output'))
            report_lines.append("```")
        else:
            report_lines.append(f"⚠️ Script failed: {no_trades_result.get('error', 'Unknown error')}")
        report_lines.append("")
    
    # Run analyze_gaps if available
    gaps_result = call_diagnostic_script('analyze_gaps', '--format', 'json')
    if gaps_result:
        report_lines.append("### analyze_gaps.py")
        if gaps_result.get('success'):
            report_lines.append("```")
            report_lines.append(gaps_result.get('stdout', 'No output')[:1000])  # Limit output
            report_lines.append("```")
        else:
            report_lines.append(f"⚠️ Script failed: {gaps_result.get('error', 'Unknown error')}")
        report_lines.append("")
    
    # Summary
    report_lines.append("## Summary")
    report_lines.append(f"- Execution trace entries: {len(entries) if 'entries' in locals() else 0}")
    report_lines.append(f"- Crash reports: {len(reports)}")
    report_lines.append("")
    
    report = "\n".join(report_lines)
    
    # Write to file if specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✓ Debug context report written to: {output_file}")
    else:
        print(report)
    
    return report


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect debug context for troubleshooting')
    parser.add_argument('--output', '-o', type=str, help='Output file path (default: stdout)')
    
    args = parser.parse_args()
    
    output_path = Path(args.output) if args.output else None
    collect_context(output_path)


if __name__ == '__main__':
    main()

