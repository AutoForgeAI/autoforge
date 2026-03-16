#!/usr/bin/env python3
"""
Test script to verify Claude usage limit detection works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from rate_limit_utils import (
    is_rate_limit_error,
    parse_claude_reset_time,
    parse_retry_after,
)

def test_usage_limit_detection():
    """Test various Claude usage limit message formats."""
    
    test_messages = [
        # Claude CLI status message
        "You've hit your limit · resets 1pm (Europe/Sofia)",
        
        # Full error message format
        "Claude usage limit reached. Your limit will reset at 3pm (America/Santiago)",
        
        # Alternative format
        "Your limit will reset at 1pm (Europe/Sofia)",
        
        # Rate limit error
        "Rate limit exceeded. Please try again later.",
        
        # Non-rate limit message (should not match)
        "Feature #1348 is in progress. Tests are passing.",
    ]
    
    print("Testing Claude usage limit detection...")
    print("=" * 60)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\nTest {i}: {message}")
        
        # Test rate limit detection
        is_rate_limit = is_rate_limit_error(message)
        print(f"  Rate limit detected: {is_rate_limit}")
        
        # Test reset time parsing
        reset_result = parse_claude_reset_time(message)
        if reset_result:
            seconds, formatted_time = reset_result
            print(f"  Reset time: {formatted_time} ({seconds} seconds)")
        else:
            print("  Reset time: Not found")
        
        # Test retry-after parsing
        retry_seconds = parse_retry_after(message)
        if retry_seconds:
            print(f"  Retry after: {retry_seconds} seconds")
        else:
            print("  Retry after: Not found")

if __name__ == "__main__":
    test_usage_limit_detection()
