"""Test IdempotencyKey security, real patterns, and dangerous characters."""

import pytest
from uuid import uuid4
from domain.value_objects import IdempotencyKey


class TestIdempotencyKeySecurity:
    """Test IdempotencyKey with security concerns and real patterns."""
    
    def test_idempotency_key_accepts_uuid4(self):
        """IdempotencyKey should accept UUID4 format."""
        uuid_key = str(uuid4())
        k = IdempotencyKey(uuid_key)
        assert len(str(k)) == 36  # Standard UUID4 length
        assert str(k) == uuid_key
    
    def test_idempotency_key_accepts_common_patterns(self):
        """IdempotencyKey should accept common real-world patterns."""
        patterns = [
            "seller123-1234567890",  # seller-timestamp
            "order-2024-01-15-001",  # order with date
            "batch-upload-20240115120000",  # batch with timestamp
            "IMPORT-CSV-" + str(uuid4())[:8],  # import with partial UUID
            "retry-3-original-key-123",  # retry pattern
        ]
        
        for pattern in patterns:
            key = IdempotencyKey(pattern)
            assert str(key) == pattern
    
    @pytest.mark.parametrize("dangerous_input", [
        "=1+1",  # Excel formula
        "=SUM(A1:A5)",  # Excel SUM
        "+SUM(A1:A5)",  # Google Sheets formula
        "@calc",  # LibreOffice formula
        "-IMPORT()",  # Minus formula
        "=cmd|'/c calc'!A1",  # Command injection attempt
        "@SUM(1:1)",  # @ formula
        "-2+3*4",  # Math expression
        "+alert(1)",  # Potential XSS
        "=1+1+cmd|' /C calc'!A0",  # Complex injection
    ])
    def test_idempotency_key_rejects_csv_injection(self, dangerous_input):
        """IdempotencyKey should reject CSV injection patterns."""
        with pytest.raises(ValueError):
            IdempotencyKey(dangerous_input)
    
    @pytest.mark.parametrize("invalid_input", [
        " " * 16,  # Only spaces
        "a" * 7,  # Too short (7 chars)
        "a" * 129,  # Too long (129 chars)
        "abc def",  # Contains space
        "abc/def",  # Contains slash
        "abc\\def",  # Contains backslash
        "abc:def",  # Contains colon (adjust if allowed)
        "abc.def",  # Contains dot (adjust if allowed)
        "abc@def",  # Contains @
        "abc#def",  # Contains hash
        "abc$def",  # Contains dollar
        "abc%def",  # Contains percent
        "abc&def",  # Contains ampersand
        "abc*def",  # Contains asterisk
        "abc(def)",  # Contains parentheses
        "abc[def]",  # Contains brackets
        "abc{def}",  # Contains braces
        "abc<def>",  # Contains angle brackets
        "abc|def",  # Contains pipe
        "abc;def",  # Contains semicolon
        "abc'def",  # Contains single quote
        'abc"def',  # Contains double quote
        "abc`def",  # Contains backtick
        "abc~def",  # Contains tilde
        "abc!def",  # Contains exclamation
        "abc?def",  # Contains question mark
        "abc,def",  # Contains comma
        "",  # Empty string
        "\t\n\r",  # Only whitespace chars
    ])
    def test_idempotency_key_rejects_invalid_characters(self, invalid_input):
        """IdempotencyKey should reject invalid characters and formats."""
        with pytest.raises(ValueError):
            IdempotencyKey(invalid_input)
    
    def test_idempotency_key_rejects_control_characters(self):
        """IdempotencyKey should reject control characters."""
        with pytest.raises(ValueError):
            IdempotencyKey("key\x00null")  # Null byte
        
        with pytest.raises(ValueError):
            IdempotencyKey("key\x1bescape")  # Escape
        
        with pytest.raises(ValueError):
            IdempotencyKey("key\x7fdelete")  # Delete
        
        with pytest.raises(ValueError):
            IdempotencyKey("key\nline")  # Newline
        
        with pytest.raises(ValueError):
            IdempotencyKey("key\ttab")  # Tab
    
    def test_idempotency_key_rejects_unicode_tricks(self):
        """IdempotencyKey should reject Unicode normalization tricks."""
        with pytest.raises(ValueError):
            IdempotencyKey("key\u200bzero")  # Zero-width space
        
        with pytest.raises(ValueError):
            IdempotencyKey("key\u202eRTL")  # Right-to-left override
        
        with pytest.raises(ValueError):
            IdempotencyKey("key\ufeffBOM")  # Byte order mark
    
    def test_idempotency_key_boundary_lengths(self):
        """Test IdempotencyKey at exact boundary lengths."""
        # Minimum valid: 8 chars (adjust based on your rules)
        min_key = IdempotencyKey("a" * 8)
        assert len(str(min_key)) == 8
        
        # Maximum valid: 128 chars
        max_key = IdempotencyKey("a" * 128)
        assert len(str(max_key)) == 128
        
        # One under minimum: 7 chars
        with pytest.raises(ValueError):
            IdempotencyKey("a" * 7)
        
        # One over maximum: 129 chars
        with pytest.raises(ValueError):
            IdempotencyKey("a" * 129)
    
    def test_idempotency_key_case_sensitivity(self):
        """IdempotencyKey should preserve case (not normalize)."""
        key = IdempotencyKey("AbC-123-XyZ")
        assert str(key) == "AbC-123-XyZ"  # Case preserved
        
        # Different case means different key
        key1 = IdempotencyKey("test-KEY-123")
        key2 = IdempotencyKey("test-key-123")
        assert key1 != key2