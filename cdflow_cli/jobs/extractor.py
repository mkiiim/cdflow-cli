# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Log extraction utility for separating import-specific logs from API logs.

This module provides functionality to extract import-related log entries
from the main API log and create separate IMPORTDONATIONS log files.
"""

import re
import os
import yaml
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..utils.config import ConfigProvider
from ..utils.paths import get_paths

# Use a logger name that will be filtered out to avoid recursive logging
logger = logging.getLogger("nbmodules.utils.log_extraction")


class ImportLogExtractor:
    """
    Extracts import-specific log entries from API logs to create separate import logs.
    """

    def __init__(self, config_provider: ConfigProvider, logging_provider=None):
        """
        Initialize the log extractor.

        Args:
            config_provider: Configuration provider instance
            logging_provider: Optional logging provider instance for getting current log file
        """
        self.config = config_provider
        self.logging_provider = logging_provider

        # Initialize paths system for direct Path operations
        from ..utils.paths import initialize_paths

        try:
            self.paths = get_paths()
            logger.debug("Using existing paths system for log extraction operations")
        except RuntimeError:
            # Paths not initialized, initialize them
            self.paths = initialize_paths(self.config)
            logger.debug("Initialized paths system for log extraction operations")

        self.patterns = self._load_patterns()
        self.extraction_settings = self._load_extraction_settings()

    def _load_patterns(self) -> Dict[str, List[str]]:
        """Load extraction patterns from configuration file."""
        try:
            # Try to load from config file first
            if hasattr(self.config, "config_path") and self.config.config_path:
                config_dir = Path(self.config.config_path).parent
            else:
                config_dir = Path("config")
            patterns_file = config_dir / "log_extraction_patterns.yaml"

            if patterns_file.exists():
                with open(patterns_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config.get("import_log_patterns", {})
            else:
                logger.warning(f"Patterns file not found: {patterns_file}, using defaults")
                return self._get_default_patterns()

        except Exception as e:
            logger.error(f"Error loading extraction patterns: {str(e)}, using defaults")
            return self._get_default_patterns()

    def _load_extraction_settings(self) -> Dict[str, Any]:
        """Load extraction settings from configuration file."""
        try:
            if hasattr(self.config, "config_path") and self.config.config_path:
                config_dir = Path(self.config.config_path).parent
            else:
                config_dir = Path("config")
            patterns_file = config_dir / "log_extraction_patterns.yaml"

            if patterns_file.exists():
                with open(patterns_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config.get("extraction_settings", {})
            else:
                return self._get_default_settings()

        except Exception as e:
            logger.error(f"Error loading extraction settings: {str(e)}, using defaults")
            return self._get_default_settings()

    def _get_default_patterns(self) -> Dict[str, List[str]]:
        """Get default extraction patterns if config file is not available."""
        return {
            "job_specific": [
                "Processing job {job_id}",
                "Job {job_id} final counts",
                "Job {job_id} completed",
                "Created job {job_id}",
            ],
            "module_specific": [
                "nbmodules.models.donation",
                "nbmodules.adapters.canadahelps",
                "nbmodules.adapters.paypal",
                "nbmodules.services.import_service",
                "nbmodules.api.jobs",
            ],
            "content_specific": [
                "PPDonationMapper",
                "CHDonationMapper",
                "Processing donation:",
                "SUCCESS create_donation",
                "Processing row",
                "Success count:",
                "Fail count:",
                "get_donationid_by_params",
                "create_donation_by_params",
                "create_person_by_params",
                "get_personid_by_params",
                "donation already existed",
                "Import complete:",
                "Successful donations:",
                "Failed donations:",
            ],
        }

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default extraction settings if config file is not available."""
        return {"time_buffer_after": 10, "max_extraction_window": 30}

    def extract_import_log(
        self, job_id: str, start_time: str, end_time: str, original_filename: Optional[str] = None
    ) -> str:
        """
        Extract import-specific logs for a job.

        Args:
            job_id: ID of the import job
            start_time: Job start time in ISO format
            end_time: Job end time in ISO format
            original_filename: Original import filename (for log naming)

        Returns:
            str: Path to the created import log file

        Raises:
            Exception: If extraction fails
        """
        logger.debug(f"Starting log extraction for job {job_id}")

        try:
            # Get current API log file
            api_log_file = self._get_current_api_log_file()
            if not api_log_file:
                raise FileNotFoundError("No current API log file found")

            # Calculate extraction time window with buffers
            start_dt, end_dt = self._calculate_extraction_window(start_time, end_time)

            # Extract matching lines
            matching_lines = self._extract_matching_lines(api_log_file, job_id, start_dt, end_dt)

            if not matching_lines:
                logger.warning(f"No matching lines found for job {job_id}")

            # Generate import log filename
            import_log_file = self._generate_import_log_filename(
                job_id, start_time, original_filename
            )

            # Write import log
            self._write_import_log(import_log_file, matching_lines)

            logger.info(
                f"Successfully extracted import log: {import_log_file} ({len(matching_lines)} lines)"
            )
            return import_log_file

        except Exception as e:
            logger.error(f"Failed to extract import log for job {job_id}: {str(e)}")
            raise

    def _get_current_api_log_file(self) -> Optional[str]:
        """Get the current API log file path."""
        # First try to get the actual current log filename from logging provider
        if self.logging_provider and hasattr(self.logging_provider, "get_current_log_filename"):
            try:
                current_log_filename = self.logging_provider.get_current_log_filename()
                if current_log_filename:
                    logger.debug(
                        f"Using actual current log file from logging provider: {current_log_filename}"
                    )
                    return current_log_filename
                else:
                    logger.debug("Logging provider returned None for current log filename")
            except Exception as e:
                logger.warning(
                    f"Error getting current log filename from logging provider: {str(e)}"
                )
        else:
            logger.debug("No logging provider available or method not supported")

        # Fallback to heuristic method if logging provider method not available
        logger.debug("Using heuristic fallback to find current log file")
        try:
            # List API log files using paths system
            # Look for both APP_*.log (unified logging) and API_APP_*.log (legacy) files
            app_log_files = [f.name for f in self.paths.logs.glob("APP_*.log")]
            api_app_log_files = [f.name for f in self.paths.logs.glob("API_APP_*.log")]
            log_files = app_log_files + api_app_log_files

            if log_files:
                # Return the most recent log file
                fallback_log = sorted(log_files)[-1]
                logger.debug(f"Using heuristic fallback log file: {fallback_log}")
                return fallback_log
            return None
        except Exception as e:
            logger.error(f"Error finding API log file: {str(e)}")
            return None

    def _calculate_extraction_window(self, start_time: str, end_time: str) -> tuple:
        """Calculate extraction time window with buffers."""
        try:
            # Parse times and add buffers
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            # Add time buffers
            # Note: We don't buffer before start time to avoid capturing previous job logs
            buffer_after = timedelta(seconds=self.extraction_settings.get("time_buffer_after", 10))

            # Use job start time without any buffer before to prevent cross-job contamination
            start_with_buffer = start_dt
            end_with_buffer = end_dt + buffer_after

            # Enforce maximum extraction window
            max_window = timedelta(
                minutes=self.extraction_settings.get("max_extraction_window", 30)
            )
            if (end_with_buffer - start_with_buffer) > max_window:
                logger.warning(f"Extraction window exceeds maximum, limiting to {max_window}")
                end_with_buffer = start_with_buffer + max_window

            return start_with_buffer, end_with_buffer

        except Exception as e:
            logger.error(f"Error calculating extraction window: {str(e)}")
            # Fallback to original times
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            return start_dt, end_dt

    def _extract_matching_lines(
        self, api_log_file: str, job_id: str, start_dt: datetime, end_dt: datetime
    ) -> List[str]:
        """Extract lines that match import patterns using direct file operations."""
        matching_lines = []

        try:
            # Get full path using paths system
            # This avoids recursive logging issues
            full_path = self._get_api_log_full_path(api_log_file)

            with open(full_path, "r", encoding="utf-8") as f:
                for line in f:
                    if self._line_matches_job(line, job_id, start_dt, end_dt):
                        matching_lines.append(line)

        except FileNotFoundError:
            logger.warning(f"API log file not found: {api_log_file}")
        except Exception as e:
            logger.error(f"Error reading API log file {api_log_file}: {str(e)}")

        return matching_lines

    def _get_api_log_full_path(self, api_log_file: str) -> str:
        """Get full path to API log file."""
        try:
            # Use paths system for direct path resolution
            return str(self.paths.logs / api_log_file)
        except Exception as e:
            logger.error(f"Error getting API log path: {str(e)}")
            # Last resort fallback
            return os.path.join("./storage_server/logs", api_log_file)

    def _line_matches_job(
        self, line: str, job_id: str, start_dt: datetime, end_dt: datetime
    ) -> bool:
        """Check if log line belongs to this import job."""
        # Extract timestamp from log line
        timestamp = self._extract_timestamp(line)
        if not timestamp:
            return False

        # Check if within time window
        if not (start_dt <= timestamp <= end_dt):
            return False

        # Check job-specific patterns (highest priority)
        job_patterns = [p.format(job_id=job_id) for p in self.patterns.get("job_specific", [])]
        if any(pattern in line for pattern in job_patterns):
            return True

        # Check module patterns (only within time window)
        if any(pattern in line for pattern in self.patterns.get("module_specific", [])):
            return True

        # Check content patterns (only within time window)
        if any(pattern in line for pattern in self.patterns.get("content_specific", [])):
            return True

        return False

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from log line."""
        # Match format: 2025-06-20 08:39:36,066
        timestamp_pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"
        match = re.match(timestamp_pattern, line)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
            except ValueError:
                pass
        return None

    def _generate_import_log_filename(
        self, job_id: str, start_time: str, original_filename: Optional[str] = None
    ) -> str:
        """Generate import log filename matching existing convention."""
        try:
            # Parse start time to get timestamp part
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            timestamp = dt.strftime("%Y%m%d-%H%M%S")

            # Use original filename if available, otherwise use generic name
            if original_filename:
                # Remove extension and use in filename
                base_name = Path(original_filename).stem
                return f"IMPORTDONATIONS_{timestamp}_{job_id}_{base_name}.log"
            else:
                return f"IMPORTDONATIONS_{timestamp}_{job_id}_extracted.log"

        except Exception as e:
            logger.error(f"Error generating import log filename: {str(e)}")
            # Fallback to simple naming
            return f"IMPORTDONATIONS_{job_id}_extracted.log"

    def _write_import_log(self, import_log_file: str, lines: List[str]) -> None:
        """Write import log using paths system."""
        try:
            if not lines:
                # Write empty file with header
                content = "# Import log extracted from API log\n# No matching lines found\n"
            else:
                # Join lines and ensure final newline
                content = "".join(lines)
                if content and not content.endswith("\n"):
                    content += "\n"

            # Write file using paths system
            file_path = self.paths.logs / import_log_file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        except Exception as e:
            logger.error(f"Error writing import log {import_log_file}: {str(e)}")
            raise


# Convenience function for external use
def extract_import_log(
    config_provider: ConfigProvider,
    job_id: str,
    start_time: str,
    end_time: str,
    original_filename: Optional[str] = None,
    logging_provider=None,
) -> str:
    """
    Convenience function to extract import log.

    Args:
        config_provider: Configuration provider instance
        job_id: ID of the import job
        start_time: Job start time in ISO format
        end_time: Job end time in ISO format
        original_filename: Original import filename (for log naming)
        logging_provider: Optional logging provider for getting current log file

    Returns:
        str: Path to the created import log file
    """
    extractor = ImportLogExtractor(config_provider, logging_provider)
    return extractor.extract_import_log(job_id, start_time, end_time, original_filename)
