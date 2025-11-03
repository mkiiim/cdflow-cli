# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
File cleanup utilities for handling problematic characters in CSV files.

This module provides utilities to clean CSV files using the 'uneff' library
to remove hidden/problematic characters that can cause import issues.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import uneff
from .file_utils import safe_read_text_file as _safe_read_text_file

logger = logging.getLogger(__name__)


class FileCleanupError(Exception):
    """Exception raised when file cleanup operations fail."""

    pass


def clean_csv_content_with_uneff(content: str, filename: str = "input.csv") -> Tuple[str, bool]:
    """
    Clean CSV content using the 'uneff' library to remove problematic characters.

    Args:
        content (str): The CSV content to clean
        filename (str): Original filename for logging purposes

    Returns:
        Tuple[str, bool]: (cleaned_content, was_modified)
            - cleaned_content: The cleaned CSV content
            - was_modified: True if content was modified, False if unchanged
    """
    try:
        # Use uneff's direct API to clean the content
        cleaned_content, char_counts = uneff.clean_content(content)

        # Check if content was actually modified
        was_modified = content != cleaned_content

        if was_modified:
            # Log details about what was cleaned
            total_chars_cleaned = sum(char_counts.values()) if char_counts else 0
            logger.info(
                f"🧹 File cleaned with uneff: {filename} ({total_chars_cleaned} problematic characters removed/replaced)"
            )
            logger.debug(f"🧹 Character cleanup details for {filename}: {char_counts}")
        else:
            logger.debug(
                f"🧹 File checked with uneff: {filename} (no problematic characters found)"
            )

        return cleaned_content, was_modified

    except Exception as e:
        logger.error(f"Error cleaning {filename} with uneff: {str(e)}")
        return content, False


def clean_csv_file_with_uneff(
    input_path: Path, output_path: Optional[Path] = None
) -> Tuple[Path, bool]:
    """
    Clean a CSV file using the 'uneff' library.

    Args:
        input_path (Path): Path to the input CSV file
        output_path (Path, optional): Path for output file. If None, modifies input_path

    Returns:
        Tuple[Path, bool]: (output_file_path, was_modified)
            - output_file_path: Path to the cleaned file
            - was_modified: True if file was modified, False if unchanged
    """
    if not input_path.exists():
        raise FileCleanupError(f"Input file does not exist: {input_path}")

    # If no output path specified, modify in place
    if output_path is None:
        output_path = input_path

    try:
        # Read original content
        original_content = _safe_read_text_file(input_path)

        # Clean using uneff's direct API
        cleaned_content, char_counts = uneff.clean_content(original_content)

        # Write cleaned content to output
        output_path.write_text(cleaned_content, encoding="utf-8")

        # Check if content was modified
        was_modified = original_content != cleaned_content

        if was_modified:
            total_chars_cleaned = sum(char_counts.values()) if char_counts else 0
            logger.info(
                f"🧹 File cleaned with uneff: {input_path.name} → {output_path.name} ({total_chars_cleaned} characters cleaned)"
            )
        else:
            logger.debug(f"🧹 File checked with uneff: {input_path.name} (no changes needed)")

        return output_path, was_modified

    except Exception as e:
        logger.error(f"Error cleaning {input_path.name} with uneff: {str(e)}")
        raise FileCleanupError(f"Cleanup failed for {input_path.name}: {str(e)}")


def get_cleanup_stats() -> Dict[str, Any]:
    """
    Get statistics about the cleanup utility availability and usage.

    Returns:
        dict: Statistics about cleanup capabilities
    """
    stats = {
        "uneff_available": True,
        "cleanup_enabled": True,  # Could be configurable later
        "tool_version": getattr(uneff, "__version__", "unknown"),
        "default_mappings_available": hasattr(uneff, "get_default_mappings_csv"),
    }

    return stats


def analyze_csv_content(content: str, filename: str = "input.csv") -> Dict[str, Any]:
    """
    Analyze CSV content for problematic characters without cleaning.

    Args:
        content (str): The CSV content to analyze
        filename (str): Original filename for logging purposes

    Returns:
        dict: Analysis results showing what would be cleaned
    """
    try:
        # Use uneff's analyze function
        analysis = uneff.analyze_content(content)

        return {
            "uneff_available": True,
            "analysis_performed": True,
            "filename": filename,
            "problematic_chars_found": len(analysis.get("issues", [])) > 0,
            "analysis_details": analysis,
        }

    except Exception as e:
        return {"uneff_available": True, "analysis_performed": False, "error": str(e)}
