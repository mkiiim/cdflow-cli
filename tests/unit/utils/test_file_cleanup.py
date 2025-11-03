# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Unit tests for file_cleanup pre-import sanitation functionality.

Tests cover CSV content cleaning, file operations, uneff integration,
and error handling scenarios.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from cdflow_cli.utils.file_cleanup import (
    clean_csv_content_with_uneff,
    clean_csv_file_with_uneff,
    get_cleanup_stats,
    analyze_csv_content,
    FileCleanupError
)


class TestFileCleanup:
    """Test file cleanup functionality."""

    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content with problematic characters."""
        return "Name,Email,Amount\nJohn Doe,john@example.com,100\nJane\x00Smith,jane@example.com,200\n"

    @pytest.fixture
    def clean_csv_content(self):
        """Clean CSV content without problematic characters."""
        return "Name,Email,Amount\nJohn Doe,john@example.com,100\nJane Smith,jane@example.com,200\n"

    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_clean_csv_content_with_modification(self, sample_csv_content):
        """Test cleaning CSV content that requires modification."""
        # Mock uneff.clean_content to return cleaned content
        cleaned_content = sample_csv_content.replace('\x00', '')
        char_counts = {'\x00': 1}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content', 
                  return_value=(cleaned_content, char_counts)):
            result_content, was_modified = clean_csv_content_with_uneff(
                sample_csv_content, "test.csv"
            )
            
            assert result_content == cleaned_content
            assert was_modified is True

    def test_clean_csv_content_no_modification(self, clean_csv_content):
        """Test cleaning CSV content that needs no modification."""
        char_counts = {}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(clean_csv_content, char_counts)):
            result_content, was_modified = clean_csv_content_with_uneff(
                clean_csv_content, "test.csv"
            )
            
            assert result_content == clean_csv_content
            assert was_modified is False

    def test_clean_csv_content_error_handling(self, sample_csv_content):
        """Test error handling during content cleaning."""
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  side_effect=Exception("Uneff error")):
            result_content, was_modified = clean_csv_content_with_uneff(
                sample_csv_content, "test.csv"
            )
            
            # Should return original content on error
            assert result_content == sample_csv_content
            assert was_modified is False

    def test_clean_csv_file_success(self, temp_file, sample_csv_content):
        """Test successful file cleaning."""
        # Write sample content to file
        temp_file.write_text(sample_csv_content, encoding='utf-8')
        
        cleaned_content = sample_csv_content.replace('\x00', '')
        char_counts = {'\x00': 1}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(cleaned_content, char_counts)):
            result_path, was_modified = clean_csv_file_with_uneff(temp_file)
            
            assert result_path == temp_file
            assert was_modified is True
            assert temp_file.read_text(encoding='utf-8') == cleaned_content

    def test_clean_csv_file_no_modification(self, temp_file, clean_csv_content):
        """Test file cleaning when no modification needed."""
        temp_file.write_text(clean_csv_content, encoding='utf-8')
        
        char_counts = {}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(clean_csv_content, char_counts)):
            result_path, was_modified = clean_csv_file_with_uneff(temp_file)
            
            assert result_path == temp_file
            assert was_modified is False

    def test_clean_csv_file_with_output_path(self, temp_file, sample_csv_content):
        """Test file cleaning with separate output file."""
        # Write sample content to input file
        temp_file.write_text(sample_csv_content, encoding='utf-8')
        
        # Create separate output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            cleaned_content = sample_csv_content.replace('\x00', '')
            char_counts = {'\x00': 1}
            
            with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                      return_value=(cleaned_content, char_counts)):
                result_path, was_modified = clean_csv_file_with_uneff(temp_file, output_path)
                
                assert result_path == output_path
                assert was_modified is True
                assert output_path.read_text(encoding='utf-8') == cleaned_content
                
                # Input file should be unchanged
                assert temp_file.read_text(encoding='utf-8') == sample_csv_content
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_clean_csv_file_nonexistent_input(self):
        """Test cleaning non-existent input file."""
        nonexistent_path = Path("/nonexistent/file.csv")
        
        with pytest.raises(FileCleanupError):
            clean_csv_file_with_uneff(nonexistent_path)

    def test_clean_csv_file_read_error(self, temp_file):
        """Test handling of file read errors."""
        temp_file.write_text("content", encoding='utf-8')
        
        with patch('cdflow_cli.utils.file_cleanup._safe_read_text_file',
                  side_effect=Exception("Read error")):
            with pytest.raises(FileCleanupError):
                clean_csv_file_with_uneff(temp_file)

    def test_clean_csv_file_write_error(self, temp_file, sample_csv_content):
        """Test handling of file write errors."""
        temp_file.write_text(sample_csv_content, encoding='utf-8')
        
        cleaned_content = sample_csv_content.replace('\x00', '')
        char_counts = {'\x00': 1}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(cleaned_content, char_counts)), \
             patch.object(Path, 'write_text', side_effect=Exception("Write error")):
            with pytest.raises(FileCleanupError):
                clean_csv_file_with_uneff(temp_file)

    def test_clean_csv_file_uneff_error(self, temp_file, sample_csv_content):
        """Test handling of uneff processing errors."""
        temp_file.write_text(sample_csv_content, encoding='utf-8')
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  side_effect=Exception("Uneff processing error")):
            with pytest.raises(FileCleanupError):
                clean_csv_file_with_uneff(temp_file)

    def test_get_cleanup_stats_success(self):
        """Test getting cleanup statistics successfully."""
        with patch('cdflow_cli.utils.file_cleanup.uneff') as mock_uneff:
            mock_uneff.__version__ = "1.2.3"
            mock_uneff.get_default_mappings_csv = Mock()
            
            stats = get_cleanup_stats()
            
            assert stats["uneff_available"] is True
            assert stats["cleanup_enabled"] is True
            assert stats["tool_version"] == "1.2.3"
            assert stats["default_mappings_available"] is True

    def test_get_cleanup_stats_no_version(self):
        """Test getting cleanup statistics when version unavailable."""
        with patch('cdflow_cli.utils.file_cleanup.uneff') as mock_uneff:
            # Remove __version__ attribute
            if hasattr(mock_uneff, '__version__'):
                delattr(mock_uneff, '__version__')
            
            stats = get_cleanup_stats()
            
            assert stats["tool_version"] == "unknown"

    def test_get_cleanup_stats_no_mappings(self):
        """Test getting cleanup statistics when mappings unavailable."""
        with patch('cdflow_cli.utils.file_cleanup.uneff') as mock_uneff:
            mock_uneff.__version__ = "1.0.0"
            # Remove get_default_mappings_csv attribute
            if hasattr(mock_uneff, 'get_default_mappings_csv'):
                delattr(mock_uneff, 'get_default_mappings_csv')
            
            stats = get_cleanup_stats()
            
            assert stats["default_mappings_available"] is False

    def test_analyze_csv_content_success(self, sample_csv_content):
        """Test successful CSV content analysis."""
        analysis_result = {
            "issues": [{"char": "\x00", "count": 1, "positions": [30]}],
            "total_issues": 1
        }
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.analyze_content',
                  return_value=analysis_result):
            result = analyze_csv_content(sample_csv_content, "test.csv")
            
            assert result["uneff_available"] is True
            assert result["analysis_performed"] is True
            assert result["filename"] == "test.csv"
            assert result["problematic_chars_found"] is True
            assert result["analysis_details"] == analysis_result

    def test_analyze_csv_content_no_issues(self, clean_csv_content):
        """Test CSV content analysis with no issues found."""
        analysis_result = {
            "issues": [],
            "total_issues": 0
        }
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.analyze_content',
                  return_value=analysis_result):
            result = analyze_csv_content(clean_csv_content, "clean.csv")
            
            assert result["problematic_chars_found"] is False
            assert result["analysis_details"]["total_issues"] == 0

    def test_analyze_csv_content_error(self, sample_csv_content):
        """Test CSV content analysis error handling."""
        with patch('cdflow_cli.utils.file_cleanup.uneff.analyze_content',
                  side_effect=Exception("Analysis error")):
            result = analyze_csv_content(sample_csv_content, "test.csv")
            
            assert result["uneff_available"] is True
            assert result["analysis_performed"] is False
            assert "error" in result
            assert result["error"] == "Analysis error"

    def test_file_cleanup_error_exception(self):
        """Test FileCleanupError exception."""
        error = FileCleanupError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_integration_clean_content_and_file(self, temp_file):
        """Test integration between content and file cleaning."""
        problematic_content = "Name,Value\nTest\x00User,123\nNormal User,456\n"
        temp_file.write_text(problematic_content, encoding='utf-8')
        
        # Mock uneff to simulate cleaning
        clean_content = problematic_content.replace('\x00', '')
        char_counts = {'\x00': 1}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(clean_content, char_counts)):
            
            # Test content cleaning
            content_result, content_modified = clean_csv_content_with_uneff(
                problematic_content, "test.csv"
            )
            
            # Test file cleaning
            file_result, file_modified = clean_csv_file_with_uneff(temp_file)
            
            assert content_modified is True
            assert file_modified is True
            assert content_result == clean_content
            assert temp_file.read_text(encoding='utf-8') == clean_content

    def test_uneff_dependency_behavior(self):
        """Test behavior when uneff module is available."""
        # Since uneff is imported at module level, test that it's accessible
        import cdflow_cli.utils.file_cleanup
        assert hasattr(cdflow_cli.utils.file_cleanup, 'uneff')

    def test_logging_behavior(self, sample_csv_content):
        """Test that appropriate logging occurs during cleaning."""
        cleaned_content = sample_csv_content.replace('\x00', '')
        char_counts = {'\x00': 1}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(cleaned_content, char_counts)), \
             patch('cdflow_cli.utils.file_cleanup.logger') as mock_logger:
            
            clean_csv_content_with_uneff(sample_csv_content, "test.csv")
            
            # Should log info about cleaning
            mock_logger.info.assert_called()
            assert "problematic characters removed/replaced" in str(mock_logger.info.call_args)

    def test_no_modification_logging(self, clean_csv_content):
        """Test logging when no modification is needed."""
        char_counts = {}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(clean_csv_content, char_counts)), \
             patch('cdflow_cli.utils.file_cleanup.logger') as mock_logger:
            
            clean_csv_content_with_uneff(clean_csv_content, "test.csv")
            
            # Should log debug about no changes
            mock_logger.debug.assert_called()
            assert "no problematic characters found" in str(mock_logger.debug.call_args)

    def test_char_counts_handling(self, sample_csv_content):
        """Test handling of character count details."""
        cleaned_content = sample_csv_content.replace('\x00', '').replace('\r', '')
        char_counts = {'\x00': 1, '\r': 2}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(cleaned_content, char_counts)):
            result_content, was_modified = clean_csv_content_with_uneff(
                sample_csv_content, "test.csv"
            )
            
            assert was_modified is True
            # Total characters cleaned should be 3 (1 + 2)

    def test_edge_case_empty_content(self):
        """Test cleaning empty content."""
        empty_content = ""
        char_counts = {}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(empty_content, char_counts)):
            result_content, was_modified = clean_csv_content_with_uneff(
                empty_content, "empty.csv"
            )
            
            assert result_content == ""
            assert was_modified is False

    def test_edge_case_very_large_content(self):
        """Test cleaning very large content."""
        large_content = "x,y,z\n" * 10000  # 10k rows
        char_counts = {}
        
        with patch('cdflow_cli.utils.file_cleanup.uneff.clean_content',
                  return_value=(large_content, char_counts)):
            result_content, was_modified = clean_csv_content_with_uneff(
                large_content, "large.csv"
            )
            
            assert len(result_content) == len(large_content)
            assert was_modified is False