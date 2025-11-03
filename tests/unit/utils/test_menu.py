# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Unit tests for TerminalMenu interactive UI components.

Tests cover menu display, keyboard navigation, file selection,
and user input validation scenarios.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from cdflow_cli.utils.menu import TerminalMenu, FileSelectionMenu


class _NullContext:
    """Simple context manager stub used to emulate blessed context managers."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeKey:
    """Lightweight keystroke double that behaves like blessed.keyboard.Keystroke."""

    def __init__(self, code=None, text=""):
        self.code = code
        self._text = text

    def __eq__(self, other):  # pragma: no cover - trivial equality helper
        if isinstance(other, FakeKey):
            return self.code == other.code and self._text == other._text
        if isinstance(other, str):
            return self._text == other
        return False

    def __repr__(self):  # pragma: no cover - debug helper
        return f"FakeKey(code={self.code!r}, text={self._text!r})"


def _make_terminal_double():
    """Create a blessed.Terminal double with callable attributes."""
    terminal = MagicMock()
    terminal.home = ""
    terminal.clear = ""
    terminal.bold_underline.side_effect = lambda x: f"BOLD_UNDERLINE({x})"
    terminal.reverse.side_effect = lambda x: f"REVERSE({x})"
    terminal.move_xy.side_effect = lambda x, y: f"MOVE({x},{y})"
    terminal.cbreak.return_value = _NullContext()
    terminal.hidden_cursor.return_value = _NullContext()
    terminal.KEY_UP = "KEY_UP"
    terminal.KEY_DOWN = "KEY_DOWN"
    terminal.KEY_ENTER = "KEY_ENTER"
    terminal.KEY_ESCAPE = "KEY_ESCAPE"
    terminal.inkey = MagicMock()
    return terminal


class TestTerminalMenu:
    """Test TerminalMenu functionality."""

    @pytest.fixture
    def mock_terminal(self):
        """Mock blessed Terminal."""
        return _make_terminal_double()

    @pytest.fixture
    def menu(self, mock_terminal):
        """Create TerminalMenu instance for testing."""
        with patch('cdflow_cli.utils.menu.blessed.Terminal', autospec=True) as terminal_cls:
            terminal_cls.return_value = mock_terminal
            return TerminalMenu("Test Menu")

    def test_menu_initialization(self, menu):
        """Test TerminalMenu initializes correctly."""
        assert menu.title == "Test Menu"
        assert menu.term is not None
        assert menu.display_formatter is not None

    def test_menu_initialization_with_formatter(self, mock_terminal):
        """Test TerminalMenu initialization with custom formatter."""
        def custom_formatter(item):
            return f"CUSTOM: {item}"

        with patch('cdflow_cli.utils.menu.blessed.Terminal', autospec=True) as terminal_cls:
            terminal_cls.return_value = mock_terminal
            menu = TerminalMenu("Test", custom_formatter)
            assert menu.display_formatter == custom_formatter

    def test_default_formatter_string(self, menu):
        """Test default formatter with string item."""
        result = menu._default_formatter("simple_string")
        assert result == "simple_string"

    def test_default_formatter_path(self, menu):
        """Test default formatter with path-like string."""
        result = menu._default_formatter("/path/to/file.txt")
        assert result == "file.txt"

    def test_default_formatter_non_string(self, menu):
        """Test default formatter with non-string item."""
        result = menu._default_formatter(123)
        assert result == "123"

    def test_display_menu(self, menu):
        """Test menu display functionality."""
        items = ["Option 1", "Option 2", "Option 3"]
        
        with patch('builtins.print') as mock_print:
            menu.display_menu(items, 1)
            
            # Verify print calls
            assert mock_print.call_count >= len(items) + 1  # Items + title

    def test_show_menu_empty_items(self, menu):
        """Test showing menu with empty items list."""
        with patch('builtins.print') as mock_print:
            result = menu.show_menu([])
            assert result is None
            mock_print.assert_called_with("No items available to select from.")

    def test_show_menu_enter_selection(self, menu, mock_terminal):
        """Test menu selection with Enter key."""
        items = ["Option 1", "Option 2", "Option 3"]
        
        # Mock key presses: down, down, enter
        mock_terminal.inkey.return_value = FakeKey(code="KEY_ENTER")
        
        with patch('builtins.print'), \
             patch.object(menu, 'display_menu'):
            result = menu.show_menu(items)
            assert result == "Option 1"  # First item (index 0)

    def test_show_menu_escape_cancel(self, menu, mock_terminal):
        """Test menu cancellation with Escape key."""
        items = ["Option 1", "Option 2"]
        
        mock_terminal.inkey.return_value = FakeKey(code="KEY_ESCAPE")
        
        with patch('builtins.print'), \
             patch.object(menu, 'display_menu'):
            result = menu.show_menu(items)
            assert result is None

    def test_show_menu_q_cancel(self, menu, mock_terminal):
        """Test menu cancellation with 'q' key."""
        items = ["Option 1", "Option 2"]
        
        mock_terminal.inkey.return_value = FakeKey(text="q")
        
        with patch('builtins.print'), \
             patch.object(menu, 'display_menu'):
            result = menu.show_menu(items)
            assert result is None

    def test_show_menu_navigation(self, menu, mock_terminal):
        """Test menu navigation with arrow keys."""
        items = ["Option 1", "Option 2", "Option 3"]
        
        # Simulate: down, down, up, enter
        key_sequence = []
        
        # Down key
        key_sequence.extend(
            [
                FakeKey(code="KEY_DOWN"),
                FakeKey(code="KEY_DOWN"),
                FakeKey(code="KEY_UP"),
                FakeKey(code="KEY_ENTER"),
            ]
        )
        
        mock_terminal.inkey.side_effect = key_sequence
        
        with patch('builtins.print'), \
             patch.object(menu, 'display_menu') as mock_display:
            result = menu.show_menu(items)
            
            # Should select second item (index 1) after navigation
            assert result == "Option 2"
            
            # Verify display was called multiple times for navigation
            assert mock_display.call_count == len(key_sequence)

    def test_show_menu_boundary_navigation(self, menu, mock_terminal):
        """Test menu navigation at boundaries."""
        items = ["Option 1", "Option 2"]
        
        # Try to go up from first item, then down, then enter
        key_sequence = []
        
        # Up key (should stay at 0)
        key_sequence.extend(
            [
                FakeKey(code="KEY_UP"),
                FakeKey(code="KEY_DOWN"),
                FakeKey(code="KEY_DOWN"),
                FakeKey(code="KEY_ENTER"),
            ]
        )
        
        mock_terminal.inkey.side_effect = key_sequence
        
        with patch('builtins.print'), \
             patch.object(menu, 'display_menu'):
            result = menu.show_menu(items)
            
            # Should select last item
            assert result == "Option 2"


class TestFileSelectionMenu:
    """Test FileSelectionMenu functionality."""

    @pytest.fixture
    def mock_terminal(self):
        """Mock blessed Terminal for file menu."""
        return _make_terminal_double()

    @pytest.fixture
    def temp_dir_with_files(self):
        """Create temporary directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files with different patterns
            (temp_path / "data_success.csv").write_text("success data")
            (temp_path / "data_failed.csv").write_text("failed data")
            (temp_path / "report.txt").write_text("report content")
            (temp_path / "config.yaml").write_text("config content")
            
            # Set different modification times
            import time
            import os
            now = time.time()
            os.utime(temp_path / "data_success.csv", (now - 100, now - 100))  # Older
            os.utime(temp_path / "data_failed.csv", (now - 50, now - 50))     # Newer
            
            yield temp_path

    @pytest.fixture
    def file_menu(self, mock_terminal):
        """Create FileSelectionMenu instance for testing."""
        with patch('cdflow_cli.utils.menu.blessed.Terminal', autospec=True) as terminal_cls:
            terminal_cls.return_value = mock_terminal
            return FileSelectionMenu("Select a file:", "*_success.csv")

    def test_file_menu_initialization(self, file_menu):
        """Test FileSelectionMenu initializes correctly."""
        assert file_menu.title == "Select a file:"
        assert file_menu.file_pattern == "*_success.csv"

    def test_file_menu_default_initialization(self, mock_terminal):
        """Test FileSelectionMenu with default parameters."""
        with patch('cdflow_cli.utils.menu.blessed.Terminal', autospec=True) as terminal_cls:
            terminal_cls.return_value = mock_terminal
            menu = FileSelectionMenu()
            assert "Select a file:" in menu.title
            assert menu.file_pattern == "*"

    def test_format_file_path(self, file_menu):
        """Test file path formatting for display."""
        result = file_menu._format_file_path("/long/path/to/file.csv")
        assert result == "file.csv"

    def test_select_file_from_directory_success(self, file_menu, temp_dir_with_files):
        """Test successful file selection from directory."""
        with patch.object(file_menu, 'show_menu', return_value=str(temp_dir_with_files / "data_success.csv")):
            result = file_menu.select_file_from_directory(str(temp_dir_with_files))
            assert result == str(temp_dir_with_files / "data_success.csv")

    def test_select_file_from_directory_nonexistent(self, file_menu):
        """Test file selection from non-existent directory."""
        with patch('builtins.print') as mock_print:
            result = file_menu.select_file_from_directory("/nonexistent/path")
            assert result is None
            mock_print.assert_called()

    def test_select_file_from_directory_no_matches(self, file_menu, temp_dir_with_files):
        """Test file selection when no files match pattern."""
        # Use pattern that won't match any files
        file_menu.file_pattern = "*.nonexistent"
        
        with patch('builtins.print') as mock_print:
            result = file_menu.select_file_from_directory(str(temp_dir_with_files))
            assert result is None
            mock_print.assert_called()

    def test_select_file_sorting_by_mtime(self, file_menu, temp_dir_with_files):
        """Test that files are sorted by modification time (newest first)."""
        # Change pattern to match both files
        file_menu.file_pattern = "*_*.csv"
        
        with patch.object(file_menu, 'show_menu') as mock_show:
            file_menu.select_file_from_directory(str(temp_dir_with_files))
            
            # Verify show_menu was called with files in correct order
            mock_show.assert_called_once()
            files_passed = mock_show.call_args[0][0]
            
            # Should have both CSV files, with newer one first
            assert len(files_passed) == 2
            assert "data_failed.csv" in files_passed[0]  # Newer file first
            assert "data_success.csv" in files_passed[1]  # Older file second

    def test_select_file_glob_pattern_matching(self, file_menu, temp_dir_with_files):
        """Test glob pattern matching works correctly."""
        # Pattern should match only success file
        result_files = list(temp_dir_with_files.glob(file_menu.file_pattern))
        assert len(result_files) == 1
        assert "data_success.csv" in str(result_files[0])

    def test_select_file_from_directory_error_handling(self, file_menu):
        """Test error handling during directory scanning."""
        with patch('pathlib.Path.glob', side_effect=Exception("Scanning error")), \
             patch('builtins.print') as mock_print:
            result = file_menu.select_file_from_directory("/some/path")
            assert result is None
            mock_print.assert_called()

    def test_file_menu_inheritance(self, file_menu):
        """Test that FileSelectionMenu properly inherits from TerminalMenu."""
        assert isinstance(file_menu, TerminalMenu)
        assert hasattr(file_menu, 'show_menu')
        assert hasattr(file_menu, 'display_menu')

    def test_format_file_path_edge_cases(self, file_menu):
        """Test file path formatting edge cases."""
        # Empty string
        assert file_menu._format_file_path("") == ""
        
        # Just filename
        assert file_menu._format_file_path("file.txt") == "file.txt"
        
        # Path with no extension
        assert file_menu._format_file_path("/path/to/filename") == "filename"
        
        # Complex path
        assert file_menu._format_file_path("/very/long/path/to/file.csv") == "file.csv"

    def test_integration_file_selection_workflow(self, file_menu, temp_dir_with_files, mock_terminal):
        """Test complete file selection workflow."""
        # Mock user selecting first file
        mock_terminal.inkey.return_value = FakeKey(code="KEY_ENTER")
        
        with patch('builtins.print'), \
             patch.object(file_menu, 'display_menu'):
            result = file_menu.select_file_from_directory(str(temp_dir_with_files))
            
            # Should return the path to the success file
            assert result is not None
            assert "data_success.csv" in result

    def test_empty_directory_handling(self, file_menu):
        """Test handling of empty directory."""
        with tempfile.TemporaryDirectory() as empty_dir:
            with patch('builtins.print') as mock_print:
                result = file_menu.select_file_from_directory(empty_dir)
                assert result is None
                mock_print.assert_called()

    def test_permission_error_handling(self, file_menu, temp_dir_with_files):
        """Test handling of permission errors during file listing."""
        # Make directory unreadable
        temp_dir_with_files.chmod(0o000)
        
        try:
            with patch('builtins.print') as mock_print:
                result = file_menu.select_file_from_directory(str(temp_dir_with_files))
                assert result is None
                mock_print.assert_called()
        finally:
            # Restore permissions for cleanup
            temp_dir_with_files.chmod(0o755)

    def test_file_pattern_variations(self, mock_terminal, temp_dir_with_files):
        """Test different file pattern variations."""
        patterns_and_expected = [
            ("*.csv", 2),  # Both CSV files
            ("*_success.*", 1),  # Only success file
            ("*.txt", 1),  # Only txt file
            ("*.nonexistent", 0),  # No matches
        ]
        
        for pattern, expected_count in patterns_and_expected:
            with patch('cdflow_cli.utils.menu.blessed.Terminal', autospec=True) as terminal_cls:
                terminal_cls.return_value = mock_terminal
                menu = FileSelectionMenu("Test", pattern)
                
                files = list(temp_dir_with_files.glob(pattern))
                assert len(files) == expected_count
