# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Utility functions for file handling in DonationFlow CLI.

This module provides helper functions for normalizing file content, including
decoding to UTF-8, removing BOM, and re-encoding to UTF-8.
"""

import logging
import chardet
from pathlib import Path
from typing import Optional

# Initialize module-level logger
logger = logging.getLogger(__name__)


def safe_read_text_file(file_path: Path) -> str:
    """
    Safely read a text file with automatic encoding detection and fallback.

    Args:
        file_path: Path to the file to read

    Returns:
        str: File content
    """
    try:
        # Try automatic encoding detection first
        with open(file_path, "rb") as f:
            sample = f.read(10000)
        result = chardet.detect(sample)
        encoding = result.get("encoding")
        confidence = result.get("confidence", 0.0)

        if encoding and confidence > 0.7:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                pass
    except Exception:
        pass

    # Try common encodings as fallbacks
    for fallback_encoding in ["utf-8", "windows-1252", "iso-8859-1"]:
        try:
            return file_path.read_text(encoding=fallback_encoding)
        except UnicodeDecodeError:
            continue

    # Final fallback with error replacement
    return file_path.read_text(encoding="utf-8", errors="replace")


def normalize_file_content(content: bytes, encoding: Optional[str] = None) -> bytes:
    """
    Normalize file content by decoding to UTF-8, removing BOM, and cleaning null bytes.

    Args:
        content (bytes): Raw file content as bytes.
        encoding (Optional[str]): Encoding to use for decoding. Defaults to 'utf-8-sig'.

    Returns:
        bytes: Normalized file content re-encoded to UTF-8.
    """
    try:
        # Default to 'utf-8-sig' to handle BOM automatically
        encoding = encoding or "utf-8-sig"

        # Decode the content
        decoded_content = content.decode(encoding, errors="replace")

        # Remove null bytes
        if "\x00" in decoded_content:
            logger.debug("Removing null bytes from file content.")
            decoded_content = decoded_content.replace("\x00", "")

        # Re-encode to UTF-8
        normalized_content = decoded_content.encode("utf-8")

        logger.debug(f"File content normalized using encoding: {encoding}")
        return normalized_content
    except Exception as e:
        logger.error(f"Error normalizing file content: {str(e)}")
        raise


def cleaned_phone(dirty_phone):
    """
    Clean a phone number by removing non-numeric characters,
    leading zeroes, and country code.

    Args:
        dirty_phone (str): Phone number to clean

    Returns:
        str: Cleaned phone number
    """
    # Remove all non-numeric characters from the phone number
    cleaned_phone = "".join(filter(str.isdigit, dirty_phone))

    # Remove leading zeroes if present
    cleaned_phone = cleaned_phone.lstrip("0")

    # Remove NA country code if present
    if cleaned_phone.startswith("1") and len(cleaned_phone) == 11:
        cleaned_phone = cleaned_phone[1:]

    return cleaned_phone
