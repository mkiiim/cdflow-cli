import pytest
import tempfile
import logging
import os
from pathlib import Path
from unittest.mock import patch, Mock


@pytest.fixture(autouse=True)
def disable_paths_system(monkeypatch):
    """Prevent logging providers from pulling in the global paths system."""
    monkeypatch.setattr('cdflow_cli.utils.paths.is_initialized', lambda: False)

    def _raise_runtime_error():
        raise RuntimeError("Paths system not initialized for tests")

    monkeypatch.setattr('cdflow_cli.utils.paths.get_paths', lambda: _raise_runtime_error())

# Import the logging utilities
from cdflow_cli.utils.logging import (
    UnifiedLoggingProvider,
    FileLoggingProvider,
    ConsoleLoggingProvider,
    PathsFileHandler,
    get_logging_provider,
    NOTICE_LEVEL,
    notice
)


class TestBasicLoggingFunctionality:
    """Test basic logging functionality that we know works."""
    
    def test_notice_level_defined(self):
        """Test that NOTICE level is properly defined."""
        assert NOTICE_LEVEL == 35
        assert logging.getLevelName(NOTICE_LEVEL) == "NOTICE"
    
    def test_notice_method_exists(self):
        """Test that notice method is added to Logger."""
        logger = logging.getLogger("test_notice")
        assert hasattr(logger, 'notice')
    
    def test_paths_file_handler_basic(self):
        """Test basic PathsFileHandler functionality."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            handler = PathsFileHandler(temp_path, mode="w")
            assert handler.log_path == temp_path
            assert handler.mode == "w"
            handler.close()
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_get_logging_provider_factory(self):
        """Test the factory function with minimal config."""
        # Test default case
        provider = get_logging_provider({})
        assert isinstance(provider, UnifiedLoggingProvider)
        
        # Test unified provider
        config = {"type": "unified"}
        provider = get_logging_provider(config)
        assert isinstance(provider, UnifiedLoggingProvider)
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logging tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_unified_logging_provider_basic_init(self, temp_log_dir):
        """Test UnifiedLoggingProvider basic initialization."""
        provider = UnifiedLoggingProvider(
            file_level="DEBUG",
            console_level="INFO",
            base_path=temp_log_dir
        )
        
        assert provider.file_level == "DEBUG"
        assert provider.console_level == "INFO"
        assert provider.log_file_path is None
    
    def test_unified_provider_get_logger(self, temp_log_dir):
        """Test getting loggers from UnifiedLoggingProvider."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        logger = provider.get_logger("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
    
    def test_unified_provider_bootstrap_logging(self, temp_log_dir):
        """Test bootstrap logging initialization."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        bootstrap_file = provider.initialize_bootstrap_logging()
        assert isinstance(bootstrap_file, str)
        assert "BOOTSTRAP" in bootstrap_file
        # File should be created
        assert os.path.exists(bootstrap_file)
    
    def test_unified_provider_operation_log(self, temp_log_dir):
        """Test operation log creation."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        op_log = provider.create_operation_log("test_operation")
        assert isinstance(op_log, str)
        assert "test_operation" in op_log
    
    def test_file_logging_provider_basic_init(self):
        """Test FileLoggingProvider basic initialization."""
        provider = FileLoggingProvider(base_path="./test_logs")
        
        # Just verify it can be created without errors
        assert isinstance(provider, FileLoggingProvider)
        # base_path may be modified by environment variables, just check it exists
        assert hasattr(provider, 'base_path')
        assert isinstance(provider.base_path, str)
    
    def test_console_logging_provider_basic_init(self):
        """Test ConsoleLoggingProvider basic initialization."""
        provider = ConsoleLoggingProvider(console_level="WARNING")
        
        # Just verify it can be created without errors
        assert isinstance(provider, ConsoleLoggingProvider)
        assert provider.console_level == "WARNING"
    
    def test_console_provider_bootstrap(self):
        """Test console provider bootstrap functionality."""
        provider = ConsoleLoggingProvider()
        
        # Console provider bootstrap should return empty string
        bootstrap_result = provider.initialize_bootstrap_logging()
        assert bootstrap_result == ""  # Console doesn't create files
    
    def test_paths_file_handler_emit(self):
        """Test PathsFileHandler emit functionality."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            handler = PathsFileHandler(temp_path, mode="w")
            handler.setFormatter(logging.Formatter("%(message)s"))
            
            # Create a test record
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            # Should not raise exception
            handler.emit(record)
            handler.close()
            
            # Verify file contains message
            if temp_path.exists():
                content = temp_path.read_text()
                assert "Test message" in content
                
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestLoggingProviderIntegration:
    """Test integration scenarios for logging providers."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for integration tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_complete_logging_workflow(self, temp_log_dir):
        """Test a complete logging workflow."""
        # Create provider
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Initialize bootstrap
        bootstrap_file = provider.initialize_bootstrap_logging()
        assert os.path.exists(bootstrap_file)
        
        # Get logger and log message
        logger = provider.get_logger("workflow_test")
        logger.info("Test workflow message")
        
        # Create operation log
        op_file = provider.create_operation_log("test_op")
        assert isinstance(op_file, str)
        
        # Shutdown should not raise
        provider.shutdown()
    
    def test_error_resilience(self, temp_log_dir):
        """Test that logging system handles errors gracefully."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Test with invalid operation name
        try:
            op_log = provider.create_operation_log("")
            # Should handle empty string gracefully
            assert isinstance(op_log, str)
        except Exception as e:
            pytest.fail(f"Should handle empty operation name gracefully: {e}")
        
        # Test logger with empty name
        try:
            empty_logger = provider.get_logger("")
            assert isinstance(empty_logger, logging.Logger)
        except Exception as e:
            pytest.fail(f"Should handle empty logger name gracefully: {e}")


class TestLoggingSecurityAndReliability:
    """Test security and reliability aspects of logging system."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for security tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_log_directory_creation_security(self):
        """Test that log directory creation is secure."""
        # Test with safe path
        safe_path = "./test_logs_safe"
        provider = UnifiedLoggingProvider(base_path=safe_path)
        
        # Should create directory safely
        bootstrap_file = provider.initialize_bootstrap_logging()
        assert isinstance(bootstrap_file, str)
        
        # Clean up
        import shutil
        if os.path.exists(safe_path):
            shutil.rmtree(safe_path)
    
    def test_logging_with_special_characters(self, temp_log_dir):
        """Test logging with special characters and unicode."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        logger = provider.get_logger("unicode_test")
        
        # Test various character sets
        test_messages = [
            "Regular ASCII message",
            "Unicode test: 测试中文字符",
            "Emoji test: 🔥 🚀 ✅",
            "Special chars: !@#$%^&*()_+-={}[]|\\:;'<>,.?/"
        ]
        
        # Should handle all message types without errors
        for msg in test_messages:
            try:
                logger.info(msg)
            except Exception as e:
                pytest.fail(f"Should handle unicode/special chars: {e}")
    
    def test_concurrent_logging_basic(self, temp_log_dir):
        """Test basic thread safety of logging system."""
        import threading
        import time
        
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        logger = provider.get_logger("concurrent_test")
        errors = []
        
        def log_worker(worker_id):
            try:
                for i in range(5):
                    logger.info(f"Worker {worker_id} message {i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))
        
        # Run multiple threads
        threads = [threading.Thread(target=log_worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        assert len(errors) == 0, f"Concurrent logging errors: {errors}"
    
    def test_logging_resource_cleanup(self, temp_log_dir):
        """Test that logging resources are cleaned up properly."""
        provider = UnifiedLoggingProvider(base_path=temp_log_dir)
        
        # Create some loggers and files
        logger1 = provider.get_logger("cleanup_test_1")
        logger2 = provider.get_logger("cleanup_test_2")
        
        bootstrap_file = provider.initialize_bootstrap_logging()
        op_file = provider.create_operation_log("cleanup_test")
        
        # Log some messages
        logger1.info("Test message 1")
        logger2.info("Test message 2")
        
        # Shutdown should clean up resources
        try:
            provider.shutdown()
        except Exception as e:
            pytest.fail(f"Shutdown should not raise exceptions: {e}")
        
        # Files should still exist after shutdown (they're just closed)
        assert os.path.exists(bootstrap_file)
        assert os.path.exists(op_file)
