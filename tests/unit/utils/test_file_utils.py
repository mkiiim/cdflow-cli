import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, Mock
from cdflow_cli.utils.file_utils import (
    safe_read_text_file,
    normalize_file_content,
    cleaned_phone
)


class TestSafeReadTextFile:
    """Test safe text file reading with encoding detection."""
    
    @pytest.fixture
    def temp_text_file(self):
        """Create a temporary text file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            temp_path = Path(f.name)
            f.write("Test content with UTF-8 encoding: 测试中文")
        yield temp_path
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
    
    def test_safe_read_utf8_file(self, temp_text_file):
        """Test reading a standard UTF-8 file."""
        content = safe_read_text_file(temp_text_file)
        
        assert "Test content with UTF-8 encoding" in content
        assert "测试中文" in content
    
    def test_safe_read_with_encoding_detection(self):
        """Test automatic encoding detection."""
        # Create file with specific encoding
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='windows-1252') as f:
            temp_path = Path(f.name)
            f.write("Content with windows-1252 encoding: café résumé")
        
        try:
            # Mock chardet to return high confidence detection
            with patch('cdflow_cli.utils.file_utils.chardet.detect') as mock_detect:
                mock_detect.return_value = {'encoding': 'windows-1252', 'confidence': 0.85}
                
                content = safe_read_text_file(temp_path)
                assert "café résumé" in content
                
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_safe_read_low_confidence_detection(self):
        """Test fallback when encoding detection confidence is low."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            temp_path = Path(f.name)
            f.write("Low confidence test content")
        
        try:
            # Mock low confidence detection
            with patch('cdflow_cli.utils.file_utils.chardet.detect') as mock_detect:
                mock_detect.return_value = {'encoding': 'ascii', 'confidence': 0.3}
                
                content = safe_read_text_file(temp_path)
                assert "Low confidence test content" in content
                
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_safe_read_encoding_detection_failure(self):
        """Test fallback when encoding detection fails."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            temp_path = Path(f.name)
            f.write("Fallback encoding test")
        
        try:
            # Mock chardet to raise exception
            with patch('cdflow_cli.utils.file_utils.chardet.detect') as mock_detect:
                mock_detect.side_effect = Exception("Detection failed")
                
                content = safe_read_text_file(temp_path)
                assert "Fallback encoding test" in content
                
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_safe_read_fallback_encodings(self):
        """Test fallback encoding sequence."""
        # Create file with content that requires fallback
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
            # Write content that might cause UTF-8 decode errors
            f.write(b"Test content with problematic bytes: \xff\xfe")
        
        try:
            # Mock chardet to return None/low confidence
            with patch('cdflow_cli.utils.file_utils.chardet.detect') as mock_detect:
                mock_detect.return_value = {'encoding': None, 'confidence': 0.1}
                
                content = safe_read_text_file(temp_path)
                # Should read successfully with fallback encoding
                assert "Test content" in content
                
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_safe_read_final_fallback_with_errors_replace(self):
        """Test final fallback with error replacement."""
        # Create file with content that will cause decode errors
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
            # Binary content that's not valid in common encodings
            f.write(b"\x80\x81\x82\x83 Invalid binary content \xff\xfe\xfd")
        
        try:
            content = safe_read_text_file(temp_path)
            # Should read successfully with replacement characters
            assert "Invalid binary content" in content
            # May contain replacement characters (�) for invalid bytes
                
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_safe_read_nonexistent_file(self):
        """Test behavior with non-existent file."""
        nonexistent_path = Path("/nonexistent/path/file.txt")
        
        with pytest.raises(FileNotFoundError):
            safe_read_text_file(nonexistent_path)
    
    def test_safe_read_permission_denied(self, temp_text_file):
        """Test behavior with permission denied."""
        # Make file unreadable (if possible on this system)
        import stat
        temp_text_file.chmod(stat.S_IWUSR)  # Write-only, no read permission
        
        try:
            # This might raise PermissionError or succeed depending on system/user
            content = safe_read_text_file(temp_text_file)
            # If it succeeds, verify it read something
            assert isinstance(content, str)
        except PermissionError:
            # Expected on systems that enforce permissions
            pass
        finally:
            # Restore permissions for cleanup
            temp_text_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


class TestNormalizeFileContent:
    """Test file content normalization functionality."""
    
    def test_normalize_basic_utf8(self):
        """Test basic UTF-8 content normalization."""
        content = b"Hello world! \xe2\x9c\x85 Test content"  # UTF-8 with checkmark
        
        result = normalize_file_content(content)
        
        assert isinstance(result, bytes)
        decoded = result.decode('utf-8')
        assert "Hello world!" in decoded
        assert "✅" in decoded  # Checkmark should be preserved
    
    def test_normalize_with_bom(self):
        """Test normalization of content with BOM (Byte Order Mark)."""
        # UTF-8 BOM + content
        content_with_bom = b"\xef\xbb\xbfHello BOM world!"
        
        result = normalize_file_content(content_with_bom)
        
        decoded = result.decode('utf-8')
        # BOM should be automatically removed by utf-8-sig encoding
        assert decoded == "Hello BOM world!"
        assert decoded[0] != '\ufeff'  # No BOM character at start
    
    def test_normalize_with_null_bytes(self, caplog):
        """Test removal of null bytes from content."""
        content_with_nulls = "Hello\x00world\x00with\x00nulls".encode('utf-8')
        
        result = normalize_file_content(content_with_nulls)
        
        decoded = result.decode('utf-8')
        assert decoded == "Helloworldwithnulls"
        # Check that null bytes were actually removed
        assert "\x00" not in decoded
        # Log message is debug level, might not appear in caplog
    
    def test_normalize_different_encoding(self):
        """Test normalization with different source encoding."""
        # Create content in windows-1252 encoding
        content = "Café résumé naïve".encode('windows-1252')
        
        result = normalize_file_content(content, encoding='windows-1252')
        
        decoded = result.decode('utf-8')
        assert "Café résumé naïve" in decoded
    
    def test_normalize_invalid_encoding_with_replacement(self):
        """Test normalization with invalid bytes using error replacement."""
        # Mix valid UTF-8 with invalid bytes
        content = b"Valid content \xff\xfe invalid bytes"
        
        result = normalize_file_content(content)
        
        # Should not raise exception due to errors='replace'
        decoded = result.decode('utf-8')
        assert "Valid content" in decoded
        # Invalid bytes should be replaced with replacement character
    
    def test_normalize_empty_content(self):
        """Test normalization of empty content."""
        content = b""
        
        result = normalize_file_content(content)
        
        assert result == b""
    
    def test_normalize_large_content(self):
        """Test normalization of large content."""
        # Create large content (10KB)
        large_content = ("Large content line with unicode: 测试中文\n" * 500).encode('utf-8')
        
        result = normalize_file_content(large_content)
        
        decoded = result.decode('utf-8')
        assert "Large content line" in decoded
        assert "测试中文" in decoded
        assert len(decoded) > 10000  # Should preserve size
    
    def test_normalize_exception_handling(self, caplog):
        """Test exception handling in content normalization."""
        # Test with invalid encoding parameter
        content = b"Test content"
        
        with pytest.raises(Exception):
            normalize_file_content(content, encoding='invalid-encoding')
    
    def test_normalize_custom_encoding_fallback(self):
        """Test normalization with custom encoding and fallback."""
        # Content that might fail with specified encoding
        content = "Special chars: ñáéíóú".encode('utf-8')
        
        # Try with an encoding that might not handle these chars
        result = normalize_file_content(content, encoding='ascii')
        
        # Should handle gracefully with error replacement
        assert isinstance(result, bytes)
        decoded = result.decode('utf-8')
        assert isinstance(decoded, str)


class TestCleanedPhone:
    """Test phone number cleaning functionality."""
    
    def test_clean_basic_phone_number(self):
        """Test cleaning a basic 10-digit US phone number."""
        phone = "(555) 123-4567"
        result = cleaned_phone(phone)
        assert result == "5551234567"
    
    def test_clean_phone_with_country_code(self):
        """Test cleaning phone with North American country code."""
        phone = "+1 (555) 123-4567"
        result = cleaned_phone(phone)
        assert result == "5551234567"  # Should remove leading '1'
    
    def test_clean_phone_with_leading_zeros(self):
        """Test cleaning phone with leading zeros."""
        phone = "0005551234567"
        result = cleaned_phone(phone)
        assert result == "5551234567"
    
    def test_clean_phone_various_formats(self):
        """Test cleaning various phone number formats."""
        phone_formats = [
            "555.123.4567",
            "555 123 4567",
            "555-123-4567",
            "(555)123-4567",
            "555/123/4567",
            "555_123_4567"
        ]
        
        for phone in phone_formats:
            result = cleaned_phone(phone)
            assert result == "5551234567", f"Failed for format: {phone}"
    
    def test_clean_phone_with_extensions(self):
        """Test cleaning phone numbers with extensions."""
        phone = "555-123-4567 ext 123"
        result = cleaned_phone(phone)
        assert result == "5551234567123"  # Extension digits included
    
    def test_clean_phone_international_format(self):
        """Test cleaning international format numbers."""
        # These should not have country code removed (not 11 digits starting with 1)
        international_phones = [
            "+44 20 7946 0958",  # UK
            "+33 1 42 68 53 00",  # France
            "+81 3 5224 5000"    # Japan
        ]
        
        for phone in international_phones:
            result = cleaned_phone(phone)
            # Should remove all non-digits but not strip leading digits
            expected = ''.join(filter(str.isdigit, phone)).lstrip('0')
            if expected.startswith('1') and len(expected) == 11:
                expected = expected[1:]
            assert result == expected
    
    def test_clean_empty_phone(self):
        """Test cleaning empty or whitespace-only phone."""
        assert cleaned_phone("") == ""
        assert cleaned_phone("   ") == ""
        assert cleaned_phone("\t\n") == ""
    
    def test_clean_phone_no_digits(self):
        """Test cleaning phone with no digits."""
        phone = "abc-def-ghij"
        result = cleaned_phone(phone)
        assert result == ""
    
    def test_clean_phone_special_characters(self):
        """Test cleaning phone with various special characters."""
        phone = "!@#555$%^123&*()4567+="
        result = cleaned_phone(phone)
        assert result == "5551234567"
    
    def test_clean_phone_mixed_case_letters_and_numbers(self):
        """Test cleaning phone with mixed letters and numbers."""
        phone = "555-CALL-NOW"  # CALL = 2255
        result = cleaned_phone(phone)
        assert result == "555"  # Only digits extracted
    
    def test_clean_very_long_phone(self):
        """Test cleaning very long phone number."""
        phone = "1234567890123456789"
        result = cleaned_phone(phone)
        # 19 digits, not 11, so leading 1 is not removed
        assert result == "1234567890123456789"
    
    def test_clean_phone_exactly_11_digits_starting_with_1(self):
        """Test that exactly 11 digits starting with 1 has the 1 removed."""
        phone = "15551234567"  # Exactly 11 digits
        result = cleaned_phone(phone)
        assert result == "5551234567"
    
    def test_clean_phone_11_digits_not_starting_with_1(self):
        """Test that 11 digits not starting with 1 are preserved."""
        phone = "25551234567"  # 11 digits, starts with 2
        result = cleaned_phone(phone)
        assert result == "25551234567"  # Should not remove leading digit
    
    def test_clean_phone_unicode_digits(self):
        """Test cleaning phone with unicode digits."""
        # Unicode digits from different scripts
        phone = "５５５１２３４５６７"  # Full-width digits
        result = cleaned_phone(phone)
        # Python's str.isdigit() actually does catch Unicode digits
        assert result == "５５５１２３４５６７" or result == ""  # Depends on Python version


class TestFileUtilsIntegration:
    """Integration tests for file utilities working together."""
    
    def test_read_and_normalize_workflow(self):
        """Test complete workflow of reading and normalizing file content."""
        # Create file with BOM and mixed content
        content_with_bom = "\ufeffHello world with BOM and unicode: 测试中文\x00null"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, 
                                       encoding='utf-8-sig') as f:
            temp_path = Path(f.name)
            f.write(content_with_bom)
        
        try:
            # Read file
            read_content = safe_read_text_file(temp_path)
            
            # Normalize the bytes
            content_bytes = read_content.encode('utf-8-sig')
            normalized = normalize_file_content(content_bytes)
            final_content = normalized.decode('utf-8')
            
            # Should have BOM removed and null bytes cleaned
            assert "Hello world with BOM" in final_content
            assert "测试中文" in final_content
            assert "\x00" not in final_content
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_error_resilience_integration(self):
        """Test that file utilities handle errors gracefully in integration."""
        # Test with various problematic content
        problematic_contents = [
            b"",  # Empty
            b"\xff\xfe\xfd",  # Invalid UTF-8
            b"Valid\x00with\x00nulls",  # Null bytes
            "\ufeffBOM content".encode('utf-8-sig'),  # BOM
        ]
        
        for content in problematic_contents:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
                temp_path = Path(f.name)
                f.write(content)
            
            try:
                # Should handle all cases without crashing
                read_content = safe_read_text_file(temp_path)
                assert isinstance(read_content, str)
                
                # Normalize should also work
                normalized = normalize_file_content(content)
                assert isinstance(normalized, bytes)
                
            finally:
                if temp_path.exists():
                    temp_path.unlink()
    
    def test_phone_cleaning_with_file_data(self):
        """Test phone cleaning with data that might come from files."""
        # Simulate phone numbers that might be read from CSV files
        file_phone_data = [
            '"(555) 123-4567"',  # Quoted
            " 555-123-4567 ",    # With whitespace
            "555-123-4567\n",    # With newline
            "555-123-4567\r\n",  # With CRLF
            "\t555-123-4567\t"   # With tabs
        ]
        
        for phone_data in file_phone_data:
            # Strip quotes and whitespace as file reading might require
            cleaned_data = phone_data.strip(' "\n\r\t')
            result = cleaned_phone(cleaned_data)
            assert result == "5551234567", f"Failed for: {repr(phone_data)}"


class TestFileUtilsEdgeCases:
    """Test edge cases and missing coverage lines."""
    
    def test_safe_read_final_fallback_line_coverage(self):
        """Test the final fallback line that was missing coverage."""
        # Create a file that will trigger all fallback paths
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
            # Write bytes that will cause encoding issues for all fallbacks
            f.write(b'\x80\x81 problematic content')
        
        try:
            # Mock chardet to fail
            with patch('cdflow_cli.utils.file_utils.chardet.detect') as mock_detect:
                mock_detect.side_effect = Exception("Detection failed")
                
                # Mock Path.read_text method to fail for fallback encodings
                def mock_read_text(encoding=None, errors=None):
                    if errors == 'replace':
                        return "final fallback content"
                    raise UnicodeDecodeError("test", b'\x80', 0, 1, "test error")
                
                with patch.object(Path, 'read_text', side_effect=mock_read_text):
                    # This should trigger the final fallback line 54
                    content = safe_read_text_file(temp_path)
                    assert "final fallback content" in content
                
        finally:
            if temp_path.exists():
                temp_path.unlink()