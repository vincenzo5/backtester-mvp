#!/usr/bin/env python3
"""
Validation script for metrics calculations.

Runs test cases with known correct answers and compares actual results
against expected values. Used for manual verification of metric calculation
correctness.

Usage:
    python scripts/tests/validate_metrics.py
    
    # Run specific test class
    python scripts/tests/validate_metrics.py --class TestBasicMetricsValidation
    
    # Run with verbose output
    python scripts/tests/validate_metrics.py --verbose
    
    # Generate report
    python scripts/tests/validate_metrics.py --report metrics_validation_report.txt
"""

import sys
import argparse
import unittest
from pathlib import Path
from io import StringIO
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.test_metrics_validation import (
    TestBasicMetricsValidation,
    TestTradeStatisticsValidation,
    TestDrawdownMetricsValidation,
    TestDayStatisticsValidation
)
from tests.test_walkforward_metrics import (
    TestOOSReturnAggregation,
    TestWalkForwardEfficiency,
    TestWalkForwardNetProfitAggregation
)
from tests.test_metrics_consistency import TestMetricsConsistency


class ValidationReporter:
    """Custom test result reporter for validation."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passed_tests = []
        self.failed_tests = []
        self.error_tests = []
        self.passed = 0
        self.failed = []
        self.errors = []
        self.total = 0
        self.start_time = None
        self.end_time = None
    
    def startTest(self, test):
        self.total += 1
        if self.verbose:
            print(f"Running: {test}")
    
    def addSuccess(self, test):
        self.passed_tests.append(test)
        self.passed += 1
        if self.verbose:
            print(f"  ✓ PASSED: {test}")
    
    def addFailure(self, test, err):
        self.failed_tests.append(test)
        self.failed.append((test, err))
        print(f"  ✗ FAILED: {test}")
        if self.verbose:
            import traceback
            traceback.print_exception(*err)
    
    def addError(self, test, err):
        self.error_tests.append(test)
        self.errors.append((test, err))
        print(f"  ✗ ERROR: {test}")
        if self.verbose:
            import traceback
            traceback.print_exception(*err)
    
    def get_report(self) -> str:
        """Generate validation report."""
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds() if self.start_time else 0
        
        report = []
        report.append("=" * 80)
        report.append("METRICS VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Duration: {duration:.2f} seconds")
        report.append("")
        
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Tests: {self.total}")
        report.append(f"Passed: {self.passed} ({self.passed/self.total*100:.1f}%)" if self.total > 0 else "Passed: 0")
        report.append(f"Failed: {len(self.failed)} ({len(self.failed)/self.total*100:.1f}%)" if self.total > 0 else "Failed: 0")
        report.append(f"Errors: {len(self.errors)} ({len(self.errors)/self.total*100:.1f}%)" if self.total > 0 else "Errors: 0")
        report.append("")
        
        if self.failed:
            report.append("FAILED TESTS")
            report.append("-" * 80)
            for test, err in self.failed:
                report.append(f"  ✗ {test}")
                report.append(f"    Error: {err[1]}")
            report.append("")
        
        if self.errors:
            report.append("ERRORS")
            report.append("-" * 80)
            for test, err in self.errors:
                report.append(f"  ✗ {test}")
                report.append(f"    Error: {err[1]}")
            report.append("")
        
        if self.passed_tests:
            report.append("PASSED TESTS")
            report.append("-" * 80)
            for test in self.passed_tests[:20]:  # Show first 20
                report.append(f"  ✓ {test}")
            if len(self.passed_tests) > 20:
                report.append(f"  ... and {len(self.passed_tests) - 20} more")
            report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def print_summary(self):
        """Print summary to console."""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {self.total}")
        if self.total > 0:
            print(f"Passed: {self.passed} ({self.passed/self.total*100:.1f}%)")
            print(f"Failed: {len(self.failed)} ({len(self.failed)/self.total*100:.1f}%)")
            print(f"Errors: {len(self.errors)} ({len(self.errors)/self.total*100:.1f}%)")
        else:
            print("No tests executed")
        print("=" * 80)
        
        if self.failed:
            print("\nFAILED TESTS:")
            for test, err in self.failed:
                print(f"  ✗ {test}")
                print(f"    {err[1]}")
        
        if self.errors:
            print("\nERRORS:")
            for test, err in self.errors:
                print(f"  ✗ {test}")
                print(f"    {err[1]}")


def run_validation_tests(test_class=None, verbose=False):
    """Run validation tests and return reporter."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestBasicMetricsValidation,
        TestTradeStatisticsValidation,
        TestDrawdownMetricsValidation,
        TestDayStatisticsValidation,
        TestOOSReturnAggregation,
        TestWalkForwardEfficiency,
        TestWalkForwardNetProfitAggregation,
        TestMetricsConsistency,
    ]
    
    if test_class:
        # Run specific class
        try:
            cls = next(cls for cls in test_classes if cls.__name__ == test_class)
            suite.addTests(loader.loadTestsFromTestCase(cls))
        except StopIteration:
            print(f"Error: Test class '{test_class}' not found")
            print(f"Available classes: {[cls.__name__ for cls in test_classes]}")
            return None
    else:
        # Run all classes
        for cls in test_classes:
            suite.addTests(loader.loadTestsFromTestCase(cls))
    
    # Create reporter
    reporter = ValidationReporter(verbose=verbose)
    reporter.start_time = datetime.now()
    
    # Run tests
    runner = unittest.TextTestRunner(stream=StringIO(), verbosity=0)
    result = runner.run(suite)
    
    # Convert result to our reporter format
    reporter.passed = result.testsRun - len(result.failures) - len(result.errors)
    reporter.failed_tests = [str(test) for test, _ in result.failures]
    reporter.error_tests = [str(test) for test, _ in result.errors]
    # For passed tests, we'll just use count (individual test tracking not needed for summary)
    reporter.passed_tests = [f"Test {i+1}" for i in range(reporter.passed)]
    reporter.failed = [(str(test), err) for test, err in result.failures]
    reporter.errors = [(str(test), err) for test, err in result.errors]
    reporter.total = result.testsRun
    
    return reporter


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate metrics calculations against known correct answers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all validation tests
  python scripts/tests/validate_metrics.py
  
  # Run specific test class
  python scripts/tests/validate_metrics.py --class TestBasicMetricsValidation
  
  # Run with verbose output
  python scripts/tests/validate_metrics.py --verbose
  
  # Generate detailed report
  python scripts/tests/validate_metrics.py --report validation_report.txt
        """
    )
    
    parser.add_argument(
        '--class', '-c',
        dest='test_class',
        help='Run specific test class'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--report', '-r',
        help='Generate detailed report file'
    )
    
    parser.add_argument(
        '--list-classes', '-l',
        action='store_true',
        help='List available test classes'
    )
    
    args = parser.parse_args()
    
    if args.list_classes:
        print("Available test classes:")
        print("  - TestBasicMetricsValidation")
        print("  - TestTradeStatisticsValidation")
        print("  - TestDrawdownMetricsValidation")
        print("  - TestDayStatisticsValidation")
        print("  - TestOOSReturnAggregation")
        print("  - TestWalkForwardEfficiency")
        print("  - TestWalkForwardNetProfitAggregation")
        print("  - TestMetricsConsistency")
        return
    
    print("Running metrics validation tests...")
    print("=" * 80)
    
    reporter = run_validation_tests(test_class=args.test_class, verbose=args.verbose)
    
    if reporter is None:
        sys.exit(1)
    
    # Print summary
    reporter.print_summary()
    
    # Generate report if requested
    if args.report:
        report_text = reporter.get_report()
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text)
        print(f"\nDetailed report saved to: {report_path}")
    
    # Exit with error code if failures
    if reporter.failed or reporter.errors:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()

