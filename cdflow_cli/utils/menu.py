# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Reusable blessed Terminal menu system for CLI tools.

Provides a keyboard-navigable menu system using the blessed library
for file selection and other interactive CLI operations.
"""

import os
import blessed
from typing import List, Optional, Callable, Any
from .console import clear_screen


class TerminalMenu:
    """Interactive terminal menu using blessed library."""

    def __init__(
        self,
        title: str = "Select an option:",
        display_formatter: Optional[Callable[[Any], str]] = None,
    ):
        """
        Initialize the terminal menu.

        Args:
            title: Menu title to display
            display_formatter: Optional function to format display items
        """
        self.title = title
        self.term = blessed.Terminal()
        self.display_formatter = display_formatter or self._default_formatter

    def _default_formatter(self, item: Any) -> str:
        """Default formatter for menu items."""
        if isinstance(item, str):
            return os.path.basename(item) if "/" in item else item
        return str(item)

    def display_menu(self, items: List[Any], selected_index: int) -> None:
        """
        Display the menu with current selection highlighted.

        Args:
            items: List of items to display
            selected_index: Currently selected index
        """
        print(self.term.home + self.term.clear)
        print(self.term.move_xy(0, 0) + self.term.bold_underline(self.title))

        for index, item in enumerate(items):
            display_text = self.display_formatter(item)
            y_position = index + 2  # +2 for title and spacing

            if index == selected_index:
                print(self.term.move_xy(0, y_position) + self.term.reverse(display_text))
            else:
                print(self.term.move_xy(0, y_position) + display_text)

    def show_menu(self, items: List[Any]) -> Optional[Any]:
        """
        Display interactive menu and return selected item.

        Args:
            items: List of items to choose from

        Returns:
            Selected item or None if cancelled
        """
        if not items:
            print("No items available to select from.")
            return None

        selected_index = 0

        with self.term.cbreak(), self.term.hidden_cursor():
            while True:
                self.display_menu(items, selected_index)
                key = self.term.inkey()

                if key.code == self.term.KEY_UP and selected_index > 0:
                    selected_index -= 1
                elif key.code == self.term.KEY_DOWN and selected_index < len(items) - 1:
                    selected_index += 1
                elif key.code == self.term.KEY_ENTER:
                    selected_item = items[selected_index]
                    print(f"\nYou selected: {self.display_formatter(selected_item)}")
                    return selected_item
                elif key.code == self.term.KEY_ESCAPE or key == "q":
                    print("\nCancelled by user.")
                    return None


class FileSelectionMenu(TerminalMenu):
    """Specialized menu for file selection."""

    def __init__(self, title: str = "Select a file:", file_pattern: str = "*"):
        """
        Initialize file selection menu.

        Args:
            title: Menu title
            file_pattern: File pattern to match (e.g., "*_success.csv")
        """
        super().__init__(title, self._format_file_path)
        self.file_pattern = file_pattern

    def _format_file_path(self, file_path: str) -> str:
        """Format file path for display (show only basename)."""
        return os.path.basename(file_path)

    def select_file_from_directory(self, directory_path: str) -> Optional[str]:
        """
        Show menu to select file from directory.

        Args:
            directory_path: Directory to scan for files

        Returns:
            Selected file path or None if cancelled
        """
        try:
            from pathlib import Path

            directory = Path(directory_path)

            if not directory.exists():
                print(f"Directory does not exist: {directory_path}")
                return None

            # Find files matching pattern
            files = list(directory.glob(self.file_pattern))

            if not files:
                print(f"No files matching pattern '{self.file_pattern}' found in {directory_path}")
                return None

            # Sort files by modification time (newest first)
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            file_paths = [str(f) for f in files]

            return self.show_menu(file_paths)

        except Exception as e:
            print(f"Error scanning directory: {str(e)}")
            return None


