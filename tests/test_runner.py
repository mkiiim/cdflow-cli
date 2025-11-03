#!/usr/bin/env python3
"""
Test runner script for the cdflow-cli test suite.

Usage:
    python tests/test_runner.py                    # Run all tests
    python tests/test_runner.py unit              # Run only unit tests
    python tests/test_runner.py integration       # Run only integration tests
    python tests/test_runner.py --coverage        # Run with coverage report
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_type=None, coverage=False, verbose=False):
    """Run the test suite with specified options."""
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add test type filter
    if test_type == 'unit':
        cmd.extend(['-m', 'unit or not integration'])
        cmd.append('tests/unit')
    elif test_type == 'integration':
        cmd.extend(['-m', 'integration'])
        cmd.append('tests/integration')
    elif test_type:
        cmd.extend(['-m', test_type])
    
    # Add coverage if requested
    if coverage:
        cmd.extend([
            '--cov=cdflow_cli',
            '--cov-report=html',
            '--cov-report=term-missing',
            '--cov-fail-under=80'
        ])
    
    # Add verbosity
    if verbose:
        cmd.append('-v')
    
    # Run the tests
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    return result.returncode


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run cdflow-cli tests')
    
    parser.add_argument(
        'test_type',
        nargs='?',
        choices=['unit', 'integration', 'manual'],
        help='Type of tests to run'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Check if pytest is available
    try:
        subprocess.run(['python', '-m', 'pytest', '--version'], 
                      check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Error: pytest is not installed. Install with: pip install pytest")
        return 1
    
    # Check if coverage is available when requested
    if args.coverage:
        try:
            subprocess.run(['python', '-m', 'pytest_cov', '--version'], 
                          check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("Error: pytest-cov is not installed. Install with: pip install pytest-cov")
            return 1
    
    # Run tests
    return run_tests(
        test_type=args.test_type,
        coverage=args.coverage,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())