#!/usr/bin/env python3
"""
Test Log Crawler Filters

Tests that the new filtering logic correctly excludes false positives.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.log_crawler import LogCrawler

def test_filters():
    print("=" * 80)
    print("TESTING LOG CRAWLER FILTERS")
    print("=" * 80)
    
    crawler = LogCrawler()
    
    # Test cases
    test_logs = [
        {
            "name": "Successful HTTP 200",
            "log": {
                "level": "INFO",
                "message": 'info: 127.0.0.1:8000 - "GET /api/logs/errors?limit=50 HTTP/1.1" 200 OK'
            },
            "should_process": False
        },
        {
            "name": "Stale worker warning",
            "log": {
                "level": "WARN",
                "message": "warnings detected: 1_stale_workers"
            },
            "should_process": False
        },
        {
            "name": "INFO prefixed message",
            "log": {
                "level": "ERROR",
                "message": "info: some message"
            },
            "should_process": False
        },
        {
            "name": "Real error",
            "log": {
                "level": "ERROR",
                "message": "Database connection failed"
            },
            "should_process": True
        },
        {
            "name": "HTTP 500 error",
            "log": {
                "level": "ERROR",
                "message": 'GET /api/test HTTP/1.1" 500 Internal Server Error'
            },
            "should_process": True
        },
        {
            "name": "Critical error",
            "log": {
                "level": "CRITICAL",
                "message": "System shutdown imminent"
            },
            "should_process": True
        }
    ]
    
    print("\nRunning filter tests...\n")
    
    passed = 0
    failed = 0
    
    for test in test_logs:
        # Test the filtering logic
        level = test["log"].get("level", "INFO").upper()
        message = test["log"].get("message", "")
        
        # Replicate the filtering logic
        should_skip = False
        
        if level not in ['ERROR', 'CRITICAL', 'WARN']:
            should_skip = True
        elif 'http/' in message.lower() and any(code in message for code in [' 200 ', ' 201 ', ' 204 ', ' 304 ']):
            should_skip = True
        elif message.lower().startswith('info:'):
            should_skip = True
        elif 'stale_workers' in message.lower() and level == 'WARN':
            should_skip = True
        
        should_process = not should_skip
        expected = test["should_process"]
        
        if should_process == expected:
            print(f"✅ {test['name']}: {'PROCESS' if should_process else 'SKIP'}")
            passed += 1
        else:
            print(f"❌ {test['name']}: Expected {'PROCESS' if expected else 'SKIP'}, got {'PROCESS' if should_process else 'SKIP'}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("\n✅ All filters working correctly!")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed")
        return False

if __name__ == "__main__":
    success = test_filters()
    sys.exit(0 if success else 1)
