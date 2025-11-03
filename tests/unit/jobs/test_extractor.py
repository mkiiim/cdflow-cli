# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Unit tests for ImportLogExtractor log parsing functionality.

Tests cover log pattern matching, time window extraction, file operations,
and configuration loading scenarios.
"""

import os
import tempfile
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

from cdflow_cli.jobs.extractor import ImportLogExtractor, extract_import_log
from cdflow_cli.utils.config import ConfigProvider
from cdflow_cli.utils.logging import LoggingProvider


class TestImportLogExtractor:
    """Test ImportLogExtractor functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration provider."""
        config = Mock(spec=ConfigProvider)
        config.config_path = "/tmp/test_config.yaml"
        return config

    @pytest.fixture
    def mock_logging(self):
        """Mock logging provider."""
        logging_provider = Mock(spec=LoggingProvider)
        logging_provider.get_current_log_filename.return_value = "APP_20250917_123456.log"
        return logging_provider

    @pytest.fixture
    def mock_paths(self):
        """Mock paths system."""
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = Mock()
            paths.logs = Path(temp_dir) / "logs"
            paths.logs.mkdir(parents=True, exist_ok=True)
            
            with patch('cdflow_cli.jobs.extractor.get_paths', return_value=paths), \
                 patch('cdflow_cli.utils.paths.initialize_paths', return_value=paths):
                yield paths

    @pytest.fixture
    def sample_log_content(self):
        """Sample log content for testing."""
        return """2025-09-17 08:39:36,066 INFO nbmodules.jobs.manager Processing job test_job_123
2025-09-17 08:39:37,100 DEBUG nbmodules.adapters.canadahelps Starting import process
2025-09-17 08:39:38,200 INFO nbmodules.services.import_service Processing row 1
2025-09-17 08:39:39,300 SUCCESS nbmodules.api.donations create_donation for test donation
2025-09-17 08:39:40,400 INFO nbmodules.jobs.manager Job test_job_123 final counts: success=5, fail=1
2025-09-17 08:39:41,500 NOTICE nbmodules.jobs.manager Job test_job_123 completed with 5 successes
2025-09-17 08:40:00,000 INFO other.module Unrelated log entry
"""

    @pytest.fixture
    def extractor(self, mock_config, mock_logging, mock_paths):
        """Create ImportLogExtractor instance for testing."""
        with patch('cdflow_cli.jobs.extractor.ImportLogExtractor._load_patterns') as mock_patterns, \
             patch('cdflow_cli.jobs.extractor.ImportLogExtractor._load_extraction_settings') as mock_settings:
            
            mock_patterns.return_value = {
                "job_specific": [
                    "Processing job {job_id}",
                    "Job {job_id} final counts",
                    "Job {job_id} completed"
                ],
                "module_specific": [
                    "nbmodules.adapters.canadahelps",
                    "nbmodules.services.import_service",
                    "nbmodules.api.donations"
                ],
                "content_specific": [
                    "Processing row",
                    "SUCCESS create_donation"
                ]
            }
            
            mock_settings.return_value = {
                "time_buffer_after": 10,
                "max_extraction_window": 30
            }
            
            return ImportLogExtractor(mock_config, mock_logging)

    def test_extractor_initialization(self, extractor, mock_config, mock_logging):
        """Test ImportLogExtractor initializes correctly."""
        assert extractor.config == mock_config
        assert extractor.logging_provider == mock_logging
        assert extractor.paths is not None
        assert extractor.patterns is not None
        assert extractor.extraction_settings is not None

    def test_load_default_patterns(self, mock_config, mock_logging, mock_paths):
        """Test loading default patterns when config file missing."""
        with patch('cdflow_cli.jobs.extractor.Path.exists', return_value=False):
            extractor = ImportLogExtractor(mock_config, mock_logging)
            patterns = extractor._get_default_patterns()
            
            assert "job_specific" in patterns
            assert "module_specific" in patterns
            assert "content_specific" in patterns
            assert "Processing job {job_id}" in patterns["job_specific"]

    def test_load_patterns_from_config(self, mock_config, mock_logging, mock_paths):
        """Test loading patterns from configuration file."""
        config_content = {
            "import_log_patterns": {
                "job_specific": ["Custom job pattern {job_id}"],
                "module_specific": ["custom.module"],
                "content_specific": ["Custom content"]
            }
        }
        
        mock_file_content = yaml.dump(config_content)
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)), \
             patch('cdflow_cli.jobs.extractor.Path.exists', return_value=True):
            
            extractor = ImportLogExtractor(mock_config, mock_logging)
            assert extractor.patterns["job_specific"] == ["Custom job pattern {job_id}"]
            assert extractor.patterns["module_specific"] == ["custom.module"]

    def test_load_default_settings(self, mock_config, mock_logging, mock_paths):
        """Test loading default extraction settings."""
        with patch('cdflow_cli.jobs.extractor.Path.exists', return_value=False):
            extractor = ImportLogExtractor(mock_config, mock_logging)
            settings = extractor._get_default_settings()
            
            assert settings["time_buffer_after"] == 10
            assert settings["max_extraction_window"] == 30

    def test_get_current_api_log_file_from_provider(self, extractor):
        """Test getting current log file from logging provider."""
        log_file = extractor._get_current_api_log_file()
        assert log_file == "APP_20250917_123456.log"

    def test_get_current_api_log_file_fallback(self, extractor, mock_paths):
        """Test fallback log file detection when provider unavailable."""
        extractor.logging_provider = None
        
        # Create some log files
        (mock_paths.logs / "APP_20250917_123456.log").touch()
        (mock_paths.logs / "API_APP_20250916_123456.log").touch()
        
        log_file = extractor._get_current_api_log_file()
        assert log_file in ["APP_20250917_123456.log", "API_APP_20250916_123456.log"]

    def test_extract_timestamp_valid(self, extractor):
        """Test extracting valid timestamp from log line."""
        line = "2025-09-17 08:39:36,066 INFO test log message"
        timestamp = extractor._extract_timestamp(line)
        
        assert timestamp is not None
        assert timestamp.year == 2025
        assert timestamp.month == 9
        assert timestamp.day == 17
        assert timestamp.hour == 8
        assert timestamp.minute == 39
        assert timestamp.second == 36

    def test_extract_timestamp_invalid(self, extractor):
        """Test extracting timestamp from invalid log line."""
        line = "Invalid log line without timestamp"
        timestamp = extractor._extract_timestamp(line)
        assert timestamp is None

    def test_calculate_extraction_window(self, extractor):
        """Test calculating extraction time window with buffers."""
        start_time = "2025-09-17T08:39:36.000000"
        end_time = "2025-09-17T08:40:00.000000"
        
        start_dt, end_dt = extractor._calculate_extraction_window(start_time, end_time)
        
        # Should not buffer before start time
        assert start_dt.isoformat() == "2025-09-17T08:39:36"
        # Should buffer after end time
        assert end_dt > datetime.fromisoformat(end_time)

    def test_calculate_extraction_window_max_limit(self, extractor):
        """Test extraction window maximum limit enforcement."""
        start_time = "2025-09-17T08:00:00.000000"
        end_time = "2025-09-17T10:00:00.000000"  # 2 hour gap
        
        start_dt, end_dt = extractor._calculate_extraction_window(start_time, end_time)
        
        # Should be limited to max_extraction_window (30 minutes)
        duration = end_dt - start_dt
        assert duration <= timedelta(minutes=30)

    def test_line_matches_job_specific_pattern(self, extractor):
        """Test line matching with job-specific patterns."""
        line = "2025-09-17 08:39:36,066 INFO Processing job test_job_123"
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matches = extractor._line_matches_job(line, "test_job_123", start_dt, end_dt)
        assert matches is True

    def test_line_matches_module_pattern(self, extractor):
        """Test line matching with module-specific patterns."""
        line = "2025-09-17 08:39:36,066 DEBUG nbmodules.adapters.canadahelps Starting import"
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matches = extractor._line_matches_job(line, "test_job_123", start_dt, end_dt)
        assert matches is True

    def test_line_matches_content_pattern(self, extractor):
        """Test line matching with content-specific patterns."""
        line = "2025-09-17 08:39:36,066 INFO Processing row 1 of CSV"
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matches = extractor._line_matches_job(line, "test_job_123", start_dt, end_dt)
        assert matches is True

    def test_line_does_not_match_outside_time_window(self, extractor):
        """Test line outside time window does not match."""
        line = "2025-09-17 08:30:00,000 INFO Processing job test_job_123"
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matches = extractor._line_matches_job(line, "test_job_123", start_dt, end_dt)
        assert matches is False

    def test_line_does_not_match_wrong_job(self, extractor):
        """Test line with wrong job ID does not match."""
        line = "2025-09-17 08:39:36,066 INFO Processing job other_job_456"
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matches = extractor._line_matches_job(line, "test_job_123", start_dt, end_dt)
        assert matches is False

    def test_extract_matching_lines(self, extractor, mock_paths, sample_log_content):
        """Test extracting matching lines from log file."""
        # Create test log file
        log_file = mock_paths.logs / "APP_20250917_123456.log"
        log_file.write_text(sample_log_content)
        
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matching_lines = extractor._extract_matching_lines(
            "APP_20250917_123456.log", "test_job_123", start_dt, end_dt
        )
        
        assert len(matching_lines) > 0
        # Should contain job-specific lines
        job_lines = [line for line in matching_lines if "test_job_123" in line]
        assert len(job_lines) >= 3  # At least the 3 job-specific lines

    def test_extract_matching_lines_missing_file(self, extractor, mock_paths):
        """Test extracting from missing log file."""
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matching_lines = extractor._extract_matching_lines(
            "nonexistent.log", "test_job_123", start_dt, end_dt
        )
        
        assert matching_lines == []

    def test_generate_import_log_filename(self, extractor):
        """Test generating import log filename."""
        start_time = "2025-09-17T08:39:36.000000"
        job_id = "test_job_123"
        original_filename = "donations_export.csv"
        
        filename = extractor._generate_import_log_filename(
            job_id, start_time, original_filename
        )
        
        assert filename.startswith("IMPORTDONATIONS_")
        assert "20250917-083936" in filename
        assert job_id in filename
        assert "donations_export" in filename
        assert filename.endswith(".log")

    def test_generate_import_log_filename_no_original(self, extractor):
        """Test generating import log filename without original filename."""
        start_time = "2025-09-17T08:39:36.000000"
        job_id = "test_job_123"
        
        filename = extractor._generate_import_log_filename(job_id, start_time)
        
        assert filename.startswith("IMPORTDONATIONS_")
        assert job_id in filename
        assert "extracted" in filename

    def test_write_import_log_with_content(self, extractor, mock_paths):
        """Test writing import log with content."""
        lines = [
            "2025-09-17 08:39:36,066 INFO Processing job test_job_123\n",
            "2025-09-17 08:39:37,100 DEBUG Starting import\n"
        ]
        
        filename = "IMPORTDONATIONS_20250917_test_job_123.log"
        extractor._write_import_log(filename, lines)
        
        log_file = mock_paths.logs / filename
        assert log_file.exists()
        
        content = log_file.read_text()
        assert "Processing job test_job_123" in content
        assert "Starting import" in content

    def test_write_import_log_empty(self, extractor, mock_paths):
        """Test writing empty import log."""
        filename = "IMPORTDONATIONS_20250917_test_job_123.log"
        extractor._write_import_log(filename, [])
        
        log_file = mock_paths.logs / filename
        assert log_file.exists()
        
        content = log_file.read_text()
        assert "# Import log extracted from API log" in content
        assert "# No matching lines found" in content

    @patch('cdflow_cli.jobs.extractor.ImportLogExtractor._get_current_api_log_file')
    @patch('cdflow_cli.jobs.extractor.ImportLogExtractor._extract_matching_lines')
    def test_extract_import_log_full_workflow(self, mock_extract_lines, mock_get_log_file, 
                                            extractor, mock_paths):
        """Test full import log extraction workflow."""
        mock_get_log_file.return_value = "APP_20250917_123456.log"
        mock_extract_lines.return_value = [
            "2025-09-17 08:39:36,066 INFO Processing job test_job_123\n"
        ]
        
        start_time = "2025-09-17T08:39:36.000000"
        end_time = "2025-09-17T08:40:00.000000"
        
        log_path = extractor.extract_import_log(
            "test_job_123", start_time, end_time, "donations.csv"
        )
        
        assert log_path.startswith("IMPORTDONATIONS_")
        assert "test_job_123" in log_path
        assert "donations" in log_path
        
        # Verify file was created
        log_file = mock_paths.logs / log_path
        assert log_file.exists()

    def test_extract_import_log_no_log_file(self, extractor):
        """Test extraction when no current log file found."""
        extractor.logging_provider = None
        
        with patch('cdflow_cli.jobs.extractor.Path.glob', return_value=[]):
            with pytest.raises(FileNotFoundError):
                extractor.extract_import_log(
                    "test_job_123", 
                    "2025-09-17T08:39:36.000000",
                    "2025-09-17T08:40:00.000000"
                )

    def test_convenience_function(self, mock_config, mock_paths):
        """Test convenience function for external use."""
        with patch('cdflow_cli.jobs.extractor.ImportLogExtractor') as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor
            mock_extractor.extract_import_log.return_value = "test_log.log"
            
            result = extract_import_log(
                config_provider=mock_config,
                job_id="test_job_123",
                start_time="2025-09-17T08:39:36.000000",
                end_time="2025-09-17T08:40:00.000000",
                original_filename="donations.csv"
            )
            
            assert result == "test_log.log"
            mock_extractor_class.assert_called_once_with(mock_config, None)
            mock_extractor.extract_import_log.assert_called_once_with(
                "test_job_123", 
                "2025-09-17T08:39:36.000000", 
                "2025-09-17T08:40:00.000000", 
                "donations.csv"
            )

    def test_error_handling_malformed_timestamp(self, extractor):
        """Test error handling for malformed timestamps."""
        start_time = "invalid-timestamp"
        end_time = "invalid-timestamp-too"
        
        # Should crash with ValueError since fallback also fails
        with pytest.raises(ValueError):
            extractor._calculate_extraction_window(start_time, end_time)

    def test_pattern_formatting_edge_cases(self, extractor):
        """Test pattern formatting with edge case job IDs."""
        # Test with job ID containing special characters
        line = "2025-09-17 08:39:36,066 INFO Processing job test-job_123.cli"
        start_dt = datetime(2025, 9, 17, 8, 39, 30)
        end_dt = datetime(2025, 9, 17, 8, 40, 0)
        
        matches = extractor._line_matches_job(line, "test-job_123.cli", start_dt, end_dt)
        assert matches is True