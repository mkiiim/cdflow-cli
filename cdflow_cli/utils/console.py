# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Console utilities for terminal output management.
"""

import os


def clear_screen():
    """Clear the terminal screen completely."""
    os.system("cls" if os.name == "nt" else "clear")


def start_fresh_output():
    """
    Create clean visual start while preserving scrollback.

    This function clears the visible screen while preserving scrollback history.
    The ANSI escape sequence clears the screen and moves cursor to home position.
    """
    print("\033[2J\033[H", end="")  # Clear screen and move to home