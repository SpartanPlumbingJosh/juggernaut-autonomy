"""
Error Fingerprinting System

Creates unique fingerprints for errors to enable deduplication and tracking.

Part of Milestone 3: Railway Logs Crawler
"""

import re
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorFingerprinter:
    """Creates fingerprints for error messages to enable deduplication."""
    
    # Patterns to normalize in error messages
    NORMALIZATION_PATTERNS = [
        # UUIDs
        (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID'),
        # Timestamps (ISO format)
        (r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', 'TIMESTAMP'),
        # Unix timestamps
        (r'\b\d{10,13}\b', 'UNIX_TIMESTAMP'),
        # IP addresses
        (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP_ADDRESS'),
        # Numbers (IDs, counts, etc)
        (r'\b\d+\b', 'NUMBER'),
        # Hex values
        (r'0x[0-9a-fA-F]+', 'HEX'),
        # File paths with line numbers
        (r':\d+:\d+', ':LINE:COL'),
        # Memory addresses
        (r'at 0x[0-9a-fA-F]+', 'at MEMORY_ADDRESS'),
    ]
    
    def normalize_message(self, message: str) -> str:
        """
        Normalize an error message by replacing variable parts.
        
        Args:
            message: Raw error message
            
        Returns:
            Normalized message
        """
        normalized = message
        
        # Apply normalization patterns
        for pattern, replacement in self.NORMALIZATION_PATTERNS:
            normalized = re.sub(pattern, replacement, normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        # Convert to lowercase for consistency
        normalized = normalized.lower()
        
        return normalized
    
    def extract_error_type(self, message: str) -> Optional[str]:
        """
        Extract error type from message.
        
        Args:
            message: Error message
            
        Returns:
            Error type (e.g., 'TypeError', 'ValueError') or None
        """
        # Common Python exceptions
        python_exceptions = [
            'TypeError', 'ValueError', 'KeyError', 'AttributeError',
            'IndexError', 'ImportError', 'RuntimeError', 'OSError',
            'IOError', 'ZeroDivisionError', 'NameError', 'SyntaxError',
            'IndentationError', 'MemoryError', 'RecursionError'
        ]
        
        for exc_type in python_exceptions:
            if exc_type.lower() in message.lower():
                return exc_type
        
        # HTTP errors
        http_pattern = r'HTTP\s+(\d{3})'
        match = re.search(http_pattern, message, re.IGNORECASE)
        if match:
            return f"HTTP_{match.group(1)}"
        
        # Database errors
        if 'database' in message.lower() or 'sql' in message.lower():
            return 'DatabaseError'
        
        # Connection errors
        if 'connection' in message.lower() or 'timeout' in message.lower():
            return 'ConnectionError'
        
        return 'UnknownError'
    
    def extract_stack_trace(self, log_message: str) -> Optional[str]:
        """
        Extract stack trace from log message if present.
        
        Args:
            log_message: Full log message
            
        Returns:
            Stack trace or None
        """
        # Look for common stack trace patterns
        lines = log_message.split('\n')
        stack_lines = []
        in_stack = False
        
        for line in lines:
            # Python stack traces
            if 'Traceback (most recent call last)' in line:
                in_stack = True
                stack_lines.append(line)
            elif in_stack:
                if line.strip().startswith('File ') or line.strip().startswith('  '):
                    stack_lines.append(line)
                elif line.strip() and not line.startswith(' '):
                    # End of stack trace
                    break
        
        if stack_lines:
            return '\n'.join(stack_lines)
        
        return None
    
    def create_fingerprint(self, message: str) -> Tuple[str, str, Optional[str]]:
        """
        Create a fingerprint for an error message.
        
        Args:
            message: Raw error message
            
        Returns:
            Tuple of (fingerprint, normalized_message, error_type)
        """
        # Normalize the message
        normalized = self.normalize_message(message)
        
        # Extract error type
        error_type = self.extract_error_type(message)
        
        # Create fingerprint (SHA256 hash of normalized message)
        fingerprint = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        
        return fingerprint, normalized, error_type
    
    def fingerprint_log(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create fingerprint for a log entry.
        
        Args:
            log_entry: Log entry with 'message', 'level', etc
            
        Returns:
            Enhanced log entry with fingerprint data
        """
        message = log_entry.get('message', '')
        
        # Create fingerprint
        fingerprint, normalized, error_type = self.create_fingerprint(message)
        
        # Extract stack trace if present
        stack_trace = self.extract_stack_trace(message)
        
        # Enhance log entry
        return {
            **log_entry,
            'fingerprint': fingerprint,
            'normalized_message': normalized,
            'error_type': error_type,
            'stack_trace': stack_trace
        }
    
    def are_similar(self, fingerprint1: str, fingerprint2: str) -> bool:
        """
        Check if two fingerprints are similar (for fuzzy matching).
        
        Args:
            fingerprint1: First fingerprint
            fingerprint2: Second fingerprint
            
        Returns:
            True if similar
        """
        # For now, exact match only
        # Could implement Levenshtein distance for fuzzy matching
        return fingerprint1 == fingerprint2


# Singleton instance
_fingerprinter = None


def get_fingerprinter() -> ErrorFingerprinter:
    """Get or create fingerprinter singleton."""
    global _fingerprinter
    if _fingerprinter is None:
        _fingerprinter = ErrorFingerprinter()
    return _fingerprinter


__all__ = ["ErrorFingerprinter", "get_fingerprinter"]
