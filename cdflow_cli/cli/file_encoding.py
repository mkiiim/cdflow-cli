#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Shared file-encoding helpers for CLI commands."""

from pathlib import Path
from typing import Tuple

import chardet


def detect_file_encoding(file_path: Path) -> Tuple[str, float]:
    """
    Detect text encoding for a given file path.

    Args:
        file_path: Fully resolved file path to inspect

    Returns:
        Tuple of (encoding, confidence)
    """
    with file_path.open("rb") as file_handle:
        sample = file_handle.read(10000)

    result = chardet.detect(sample)
    return result["encoding"], result["confidence"]
