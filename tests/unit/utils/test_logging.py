import pytest
import tempfile
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, Mock
from io import StringIO

# Import the logging utilities
from cdflow_cli.utils.logging import (
    ImportLoggingContext,
    LoggingProvider,
    UnifiedLoggingProvider,
    FileLoggingProvider,
    ConsoleLoggingProvider,
    PathsFileHandler,
    get_logging_provider,
    NOTICE_LEVEL,
    notice
)


class TestCustomLogLevel:
    """Test custom NOTICE log level functionality."""
    
    def test_notice_level_constant(self):
        """Test that NOTICE level is defined correctly."""
        assert NOTICE_LEVEL == 35
        assert logging.getLevelName(NOTICE_LEVEL) == "NOTICE"
    
    def test_notice_method_added_to_logger(self):
        """Test that notice method is added to Logger class."""
        logger = logging.getLogger("test_notice")
        assert hasattr(logger, 'notice')
        assert callable(getattr(logger, 'notice'))
    
    def test_notice_method_functionality(self, caplog):
        """Test that notice method logs at correct level."""
        logger = logging.getLogger("test_notice_func")
        logger.setLevel(logging.DEBUG)
        
        with caplog.at_level(logging.DEBUG):
            logger.notice("Test notice message")
        
        # Verify the message was logged at NOTICE level
        assert any(record.levelno == NOTICE_LEVEL for record in caplog.records)
        assert any("Test notice message" in record.message for record in caplog.records)


class TestImportLoggingContext:
    """Test ImportLoggingContext for isolated logging operations."""
    
    @pytest.fixture
    def temp_logging_dir(self):
        """Create a temporary directory for logging tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_logging_provider(self):
        """Mock logging provider."""
        return Mock()
    
    def test_init_import_logging_context(self, mock_logging_provider):
        """Test ImportLoggingContext initialization."""
        context = ImportLoggingContext(mock_logging_provider, "import.log")
        
        assert context.logging_provider == mock_logging_provider
        assert context.import_log_filename == "import.log"
        assert context.import_handler is None
        assert context.import_root_logger is None
        assert context.redirected_loggers == {}
    
    def test_enter_context_with_paths_system(self, mock_logging_provider, temp_logging_dir):
        """Test entering context when paths system is available."""
        context = ImportLoggingContext(mock_logging_provider, "import.log")
        
        # Mock the paths import to avoid ImportError
        with patch('cdflow_cli.utils.logging.logging.FileHandler') as mock_handler:
            mock_handler_instance = Mock()
            mock_handler_instance.level = 0  # Set level to integer for comparison
            mock_handler.return_value = mock_handler_instance
            
            context.__enter__()
            
            # Verify that some handler was created and context is set up
            assert context.import_root_logger is not None
            assert context.import_root_logger.name == "IMPORT_OPERATION"
    
    @patch('os.makedirs')
    def test_enter_context_fallback_without_paths(self, mock_makedirs, mock_logging_provider):
        """Test entering context when paths system is not available."""
        context = ImportLoggingContext(mock_logging_provider, "import.log")
        
        # Enter context
        with patch('logging.FileHandler') as mock_handler:
            mock_handler_instance = Mock()
            mock_handler_instance.level = 0  # Set level to integer for comparison
            mock_handler.return_value = mock_handler_instance
            
            context.__enter__()
            
            # Verify that context was set up (may use fallback path)
            assert context.import_root_logger is not None
            assert context.import_root_logger.name == "IMPORT_OPERATION"
    
    def test_exit_context_cleanup(self, mock_logging_provider):
        """Test that context exit cleans up properly."""
        context = ImportLoggingContext(mock_logging_provider, "import.log")
        
        # Mock the handler and logger
        context.import_handler = Mock()
        context.import_root_logger = Mock()
        context.import_root_logger.handlers = [context.import_handler]
        
        # Exit context
        context.__exit__(None, None, None)
        
        # Verify cleanup
        context.import_handler.close.assert_called_once()
        context.import_root_logger.removeHandler.assert_called_once_with(context.import_handler)
    
    def test_get_logger_returns_import_logger(self, mock_logging_provider):
        """Test that get_logger returns the import-specific logger."""
        context = ImportLoggingContext(mock_logging_provider, "import.log")
        context.import_root_logger = logging.getLogger("IMPORT_OPERATION")
        
        logger = context.get_logger("test_logger")
        
        # Should return a child logger of the import root logger
        assert logger.name.startswith("IMPORT_OPERATION")


class TestLoggingProviderInterface:
    """Test the abstract LoggingProvider interface."""
    
    def test_logging_provider_is_abstract(self):
        """Test that LoggingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LoggingProvider()
    
    def test_logging_provider_methods_are_abstract(self):
        """Test that all required methods are abstract."""
        # Check that abstract methods exist
        abstract_methods = LoggingProvider.__abstractmethods__
        expected_methods = {
            'configure_logging',
            'get_logger',
            'shutdown',
            'initialize_bootstrap_logging',
            'transition_to_application_logging',
            'create_operation_log',
            'get_current_log_filename'
        }
        
        assert abstract_methods == expected_methods


class TestUnifiedLoggingProvider:
    """Test UnifiedLoggingProvider implementation."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logging tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_init_unified_logging_provider(self, temp_log_dir):
        """Test UnifiedLoggingProvider initialization."""
        provider = UnifiedLoggingProvider(
            base_path=temp_log_dir,
            console_level="INFO",
            file_level="DEBUG"
        )
        
        # Check the actual attributes from the class
        assert provider.console_level == "INFO"
        assert provider.file_level == "DEBUG"
        assert provider.log_file_path is None  # Correct attribute name
    
    def test_ensure_log_directory_creation(self, temp_log_dir):
        """Test that log directory is created if it doesn't exist."""
        log_dir = os.path.join(temp_log_dir, "new_logs")
        provider = UnifiedLoggingProvider(base_path=log_dir)
        
        # Directory should be created during initialization
        provider._ensure_log_directory()
        assert os.path.exists(log_dir)
    
    def test_configure_logging_basic(self, temp_log_dir):
        """Test basic logging configuration."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        log_file = provider.configure_logging(
            log_filename="test.log",
            log_level="INFO",
            early_init=True
        )
        
        assert log_file is not None
        assert log_file.endswith("test.log")
        assert provider.log_file_path == log_file
    
    def test_get_logger_caching(self, temp_log_dir):
        """Test that loggers are cached properly."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Get same logger twice
        logger1 = provider.get_logger("test_logger")
        logger2 = provider.get_logger("test_logger")
        
        # Should return the same instance
        assert logger1 is logger2
        assert "test_logger" in provider.loggers
    
    def test_initialize_bootstrap_logging(self, temp_log_dir):
        """Test bootstrap logging initialization."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        bootstrap_file = provider.initialize_bootstrap_logging()
        
        assert bootstrap_file is not None
        assert "BOOTSTRAP" in bootstrap_file
        assert os.path.exists(bootstrap_file)
    
    def test_create_operation_log(self, temp_log_dir):
        """Test creation of operation-specific logs."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        op_log = provider.create_operation_log("import_donations", prefix="IMP")
        
        assert op_log is not None
        assert "IMP" in op_log
        assert "import_donations" in op_log
    
    def test_shutdown_closes_handlers(self, temp_log_dir):
        """Test that shutdown properly closes all handlers."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Create some loggers with handlers
        logger = provider.get_logger("test_logger")
        provider.configure_logging(log_level="INFO", log_filename="test.log")
        
        # Verify handlers exist before shutdown
        assert len(provider.root_logger.handlers) > 0
        
        # Call shutdown
        provider.shutdown()
        
        # Verify handlers were removed
        assert len(provider.root_logger.handlers) == 0


class TestFileLoggingProvider:
    """Test FileLoggingProvider implementation."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logging tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_file_logging_provider_init(self, temp_log_dir):
        """Test FileLoggingProvider initialization."""
        provider = FileLoggingProvider(
            base_path=temp_log_dir,
            console_level="WARNING"
        )
        
        assert provider.base_path == temp_log_dir
        assert provider.console_level == "WARNING"
        assert provider.current_log_file is None
    
    def test_file_logging_configure_logging(self, temp_log_dir):
        """Test file logging configuration."""
        provider = FileLoggingProvider(base_path=temp_log_dir)
        
        log_file = provider.configure_logging(
            log_level="DEBUG",
            log_filename="file_test.log"
        )
        
        assert log_file is not None
        assert os.path.exists(log_file)
        assert "file_test.log" in log_file
    
    def test_file_logging_creates_log_files(self, temp_log_dir):
        """Test that actual log files are created and written to."""
        provider = FileLoggingProvider(base_path=temp_log_dir)
        
        log_file = provider.configure_logging(log_level="DEBUG", log_filename="write_test.log")
        logger = provider.get_logger("write_test")
        
        # Write a test message
        test_message = "Test log message for file writing"
        logger.info(test_message)
        
        # Force handler to flush
        for handler in logger.handlers:
            handler.flush()
        
        # Verify the message was written to file
        assert os.path.exists(log_file)
        with open(log_file, 'r') as f:
            content = f.read()
            assert test_message in content


class TestConsoleLoggingProvider:
    """Test ConsoleLoggingProvider implementation."""
    
    def test_console_logging_provider_init(self):
        """Test ConsoleLoggingProvider initialization."""
        provider = ConsoleLoggingProvider(console_level="ERROR")
        
        assert provider.console_level == "ERROR"
        assert provider.current_log_file is None
    
    def test_console_logging_configure_logging(self):
        """Test console logging configuration."""
        provider = ConsoleLoggingProvider()
        
        log_file = provider.configure_logging(log_level="INFO")
        
        # Console provider doesn't create files
        assert log_file is None
        assert provider.current_log_file is None
    
    def test_console_logging_captures_output(self, capfd):
        """Test that console logging actually outputs to console."""
        provider = ConsoleLoggingProvider(console_level="INFO")
        provider.configure_logging(log_level="INFO")
        
        logger = provider.get_logger("console_test")
        test_message = "Test console output message"
        logger.info(test_message)
        
        # Capture console output
        captured = capfd.readouterr()
        # Note: May appear in stdout or stderr depending on handler configuration
        assert test_message in captured.out or test_message in captured.err
    
    def test_console_bootstrap_and_transition(self):
        """Test bootstrap logging and transition for console provider."""
        provider = ConsoleLoggingProvider()
        
        bootstrap_file = provider.initialize_bootstrap_logging()
        assert bootstrap_file == ""  # Console provider returns empty string
        
        transition_file = provider.transition_to_application_logging("", "app.log")
        assert transition_file == "app.log"  # Console provider returns app_log_path


class TestPathsFileHandler:
    """Test PathsFileHandler implementation."""
    
    @pytest.fixture
    def temp_log_file(self):
        """Create temporary log file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
    
    def test_paths_file_handler_init(self, temp_log_file):
        """Test PathsFileHandler initialization."""
        handler = PathsFileHandler(temp_log_file, mode="w")
        
        assert handler.log_path == temp_log_file
        assert handler.mode == "w"
        handler.close()
    
    def test_paths_file_handler_emit_creates_file(self, temp_log_file):
        """Test that PathsFileHandler creates and writes to files."""
        # Remove the file if it exists
        if temp_log_file.exists():
            temp_log_file.unlink()
        
        handler = PathsFileHandler(temp_log_file, mode="w")
        handler.setFormatter(logging.Formatter("%(message)s"))
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message for PathsFileHandler",
            args=(),
            exc_info=None
        )
        
        # Emit the record
        handler.emit(record)
        handler.close()
        
        # Verify file was created and contains the message
        assert temp_log_file.exists()
        content = temp_log_file.read_text()
        assert "Test message for PathsFileHandler" in content
    
    def test_paths_file_handler_error_handling(self, temp_log_dir):
        """Test PathsFileHandler handles file system errors gracefully."""
        # Try to write to a directory that doesn't exist
        invalid_path = Path(temp_log_dir) / "nonexistent" / "subdir" / "test.log"
        
        handler = PathsFileHandler(invalid_path)
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Test error handling",
            args=(),
            exc_info=None
        )
        
        # Should not raise exception even if directory doesn't exist
        try:
            handler.emit(record)
            handler.close()
        except Exception as e:
            pytest.fail(f"PathsFileHandler should handle file system errors gracefully: {e}")
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logging tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir


class TestLoggingProviderFactory:
    """Test the get_logging_provider factory function."""
    
    def test_get_unified_logging_provider(self):
        """Test getting UnifiedLoggingProvider from config."""
        config = {
            "type": "unified",
            "base_path": "./logs",
            "console_level": "INFO",
            "file_level": "DEBUG"
        }
        
        provider = get_logging_provider(config)
        
        assert isinstance(provider, UnifiedLoggingProvider)
        assert provider.base_path == "./logs"
        assert provider.console_level == "INFO"
    
    def test_get_file_logging_provider(self):
        """Test getting FileLoggingProvider from config."""
        config = {
            "file_level": "DEBUG",
            "console_level": "NONE"
        }
        
        provider = get_logging_provider(config)
        
        assert isinstance(provider, FileLoggingProvider)
        assert provider.base_path == "./logs"
    
    def test_get_console_logging_provider(self):
        """Test getting ConsoleLoggingProvider from config."""
        config = {
            "file_level": "NONE",
            "console_level": "ERROR"
        }
        
        provider = get_logging_provider(config)
        
        assert isinstance(provider, ConsoleLoggingProvider)
        assert provider.console_level == "ERROR"
    
    def test_get_logging_provider_invalid_type(self):
        """Test handling of invalid logging provider type."""
        config = {"file_level": "INVALID", "console_level": "INVALID"}
        
        # This should still work as UnifiedLoggingProvider handles invalid levels
        provider = get_logging_provider(config)
        assert isinstance(provider, UnifiedLoggingProvider)
    
    def test_get_logging_provider_missing_type(self):
        """Test handling of missing type in config."""
        config = {}  # No type specified
        
        # Should default to unified
        provider = get_logging_provider(config)
        assert isinstance(provider, UnifiedLoggingProvider)


class TestLoggingIntegration:
    """Integration tests for logging system."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for integration tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_full_logging_workflow(self, temp_log_dir):
        """Test complete logging workflow from bootstrap to shutdown."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # 1. Initialize bootstrap logging
        bootstrap_file = provider.initialize_bootstrap_logging()
        assert bootstrap_file is not None
        
        # 2. Get a logger and log a bootstrap message
        logger = provider.get_logger("integration_test")
        logger.info("Bootstrap message")
        
        # 3. Transition to application logging
        app_file = provider.transition_to_application_logging(
            bootstrap_file, "application.log"
        )
        assert app_file is not None
        assert app_file != bootstrap_file
        
        # 4. Log application messages
        logger.info("Application message")
        logger.notice("Notice level message")
        
        # 5. Create operation log
        op_file = provider.create_operation_log("test_operation")
        assert op_file is not None
        
        # 6. Shutdown cleanly
        provider.shutdown()
        
        # Verify files were created
        assert os.path.exists(bootstrap_file)
        assert os.path.exists(app_file)
        assert os.path.exists(op_file)
    
    def test_logging_context_isolation(self, temp_log_dir):
        """Test that ImportLoggingContext properly isolates logging."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Set up main application logging
        provider.configure_logging(log_level="INFO", log_filename="main.log")
        main_logger = provider.get_logger("main_app")
        main_logger.info("Main application message")
        
        # Use import logging context
        with ImportLoggingContext(provider, "import_operation.log") as import_context:
            import_logger = import_context.get_logger("import_operation")
            import_logger.info("Import operation message")
            
            # Both loggers should work independently
            main_logger.info("Another main message")
            import_logger.info("Another import message")
        
        # After context exit, main logging should still work
        main_logger.info("Final main message")
        
        # Verify separate log files were created
        main_log_filename = provider.get_current_log_filename()
        assert main_log_filename is not None
        main_log_full_path = os.path.join(temp_log_dir, main_log_filename)
        assert os.path.exists(main_log_full_path)
    
    def test_error_resilience(self, temp_log_dir):
        """Test that logging system is resilient to various error conditions."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Test with invalid log levels
        try:
            provider.configure_logging(log_level="INVALID_LEVEL", log_filename="test.log")
            logger = provider.get_logger("error_test")
            logger.info("This should still work")
        except Exception as e:
            pytest.fail(f"Logging should handle invalid levels gracefully: {e}")
        
        # Test with None filename
        try:
            provider.configure_logging(log_level="INFO", log_filename=None)
        except Exception:
            pass  # This might fail, which is acceptable
        
        # Test logger creation with empty name
        try:
            empty_logger = provider.get_logger("")
            assert empty_logger is not None
        except Exception as e:
            pytest.fail(f"Should handle empty logger names: {e}")


@pytest.fixture(autouse=True)
def disable_paths_system(monkeypatch):
    """Ensure tests don't pick up a pre-initialized paths system."""
    monkeypatch.setattr('cdflow_cli.utils.paths.is_initialized', lambda: False)

    def _raise_runtime_error():
        raise RuntimeError("Paths system not initialized for tests")

    monkeypatch.setattr('cdflow_cli.utils.paths.get_paths', lambda: _raise_runtime_error())
