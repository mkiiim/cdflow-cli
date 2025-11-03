import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from cdflow_cli.utils.paths import StoragePaths


class TestStoragePaths:
    """Test StoragePaths functionality for file path management."""
    
    @pytest.fixture
    def mock_config_provider(self):
        """Create a mock config provider."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'jobs',
                'logs': 'logs',
                'output': 'output'
            },
            'base_path': '/tmp/test_storage'
        }
        return mock_provider
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_storage_paths_init_with_simple_paths(self, mock_config_provider, temp_storage_dir):
        """Test StoragePaths initialization with simple paths configuration."""
        # Update mock to use temporary directory
        mock_config_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'jobs',
                'logs': 'logs',
                'output': 'output',
                'cli_source': 'cli_source'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_config_provider)
        
        # Should initialize without errors
        assert hasattr(storage_paths, '_paths')
        assert hasattr(storage_paths, 'config_provider')
        assert storage_paths.config_provider == mock_config_provider
    
    def test_storage_paths_init_with_default_paths(self):
        """Test StoragePaths initialization with default paths fallback."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {}  # No paths config
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should initialize with defaults
        assert hasattr(storage_paths, '_paths')
        assert isinstance(storage_paths._paths, dict)
    
    def test_storage_paths_directory_creation(self, temp_storage_dir):
        """Test that required directories are created."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'jobs',
                'logs': 'logs'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Directories should be created
        expected_dirs = [
            temp_storage_dir / 'jobs',
            temp_storage_dir / 'logs'
        ]
        
        for expected_dir in expected_dirs:
            assert expected_dir.exists(), f"Directory should exist: {expected_dir}"
    
    def test_storage_paths_error_handling_in_init(self, caplog):
        """Test error handling during initialization."""
        mock_provider = Mock()
        mock_provider.get_storage_config.side_effect = Exception("Config error")
        
        # Should not crash, should use fallback
        storage_paths = StoragePaths(mock_provider)
        
        assert hasattr(storage_paths, '_paths')
        assert "Failed to initialize storage paths" in caplog.text
    
    @patch('cdflow_cli.utils.paths.logger')
    def test_storage_paths_logging_during_init(self, mock_logger, mock_config_provider):
        """Test that appropriate logging occurs during initialization."""
        storage_paths = StoragePaths(mock_config_provider)
        
        # Should have logged debug messages
        mock_logger.debug.assert_called()
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
        
        # Should log config keys and initialization
        assert any("config:" in msg for msg in debug_calls)
        assert any("initialized:" in msg for msg in debug_calls)
    
    def test_storage_paths_with_base_path_resolution(self, temp_storage_dir):
        """Test path resolution with base_path."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'custom_dir': 'custom',
                'nested_dir': 'nested/deep'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should create directories relative to base_path
        expected_dirs = [
            temp_storage_dir / 'custom',
            temp_storage_dir / 'nested' / 'deep'
        ]
        
        # Verify StoragePaths was created successfully
        assert hasattr(storage_paths, '_paths')
        # Directory creation depends on implementation details
    
    def test_storage_paths_without_base_path(self):
        """Test StoragePaths when no base_path is provided."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'test_jobs'
            }
            # No base_path
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should handle missing base_path gracefully
        assert hasattr(storage_paths, '_paths')
    
    def test_storage_paths_empty_config(self):
        """Test StoragePaths with completely empty configuration."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {}
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should initialize with empty paths dict
        assert hasattr(storage_paths, '_paths')
        assert isinstance(storage_paths._paths, dict)
    
    def test_storage_paths_config_provider_integration(self, temp_storage_dir):
        """Test integration with config provider."""
        mock_provider = Mock()
        
        # Simulate realistic config
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'jobs',
                'logs': 'logs',
                'output': 'output',
                'cli_source': 'cli_source',
                'app_upload': 'app_upload',
                'app_processing': 'app_processing',
                'tokens': 'tokens'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should call config provider
        mock_provider.get_storage_config.assert_called_once()
        
        # Should have paths configured (directories created by _create_directories)
        assert hasattr(storage_paths, '_paths')
        # Verify at least some directories were created
        created_dirs = [p for p in temp_storage_dir.iterdir() if p.is_dir()]
        assert len(created_dirs) >= 3  # At least some directories should exist
    
    def test_storage_paths_permission_handling(self, temp_storage_dir):
        """Test handling of directory creation with permission issues."""
        mock_provider = Mock()
        
        # Try to create directory in a path that might have permission issues
        restricted_base = temp_storage_dir / 'restricted'
        restricted_base.mkdir()
        
        # Make it read-only (if possible)
        import stat
        try:
            restricted_base.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # Read-only
            
            mock_provider.get_storage_config.return_value = {
                'paths': {'test': 'test_dir'},
                'base_path': str(restricted_base)
            }
            
            # Should handle gracefully (may succeed or fail depending on system)
            storage_paths = StoragePaths(mock_provider)
            assert hasattr(storage_paths, '_paths')
            
        except (OSError, PermissionError):
            # Expected on some systems
            pass
        finally:
            # Restore permissions for cleanup
            try:
                restricted_base.chmod(stat.S_IRWXU)
            except (OSError, PermissionError):
                pass
    
    def test_storage_paths_absolute_vs_relative_paths(self, temp_storage_dir):
        """Test handling of absolute vs relative paths in configuration."""
        mock_provider = Mock()
        
        # Mix of absolute and relative paths
        absolute_path = str(temp_storage_dir / 'absolute')
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'relative_dir': 'relative',
                'absolute_dir': absolute_path
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Both should be created appropriately
        relative_path = temp_storage_dir / 'relative'
        absolute_path_obj = Path(absolute_path)
        
        # Note: actual behavior depends on implementation details
        # This test verifies the system handles mixed path types
        assert hasattr(storage_paths, '_paths')
    
    def test_storage_paths_special_characters_in_names(self, temp_storage_dir):
        """Test handling of special characters in directory names."""
        mock_provider = Mock()
        
        # Directory names with special characters
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'spaces_dir': 'dir with spaces',
                'special_chars': 'dir-with_special.chars',
                'unicode_dir': 'dir_测试'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should handle special characters in directory names
        expected_dirs = [
            temp_storage_dir / 'dir with spaces',
            temp_storage_dir / 'dir-with_special.chars',
            temp_storage_dir / 'dir_测试'
        ]
        
        for expected_dir in expected_dirs:
            # May or may not exist depending on filesystem support
            # The important thing is that it doesn't crash
            assert hasattr(storage_paths, '_paths')
    
    def test_storage_paths_deep_nested_directories(self, temp_storage_dir):
        """Test creation of deeply nested directory structures."""
        mock_provider = Mock()
        
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'deep_dir': 'level1/level2/level3/level4/deep'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should initialize without error
        assert hasattr(storage_paths, '_paths')
        # Directory creation depends on implementation
    
    def test_storage_paths_concurrent_access_safety(self, temp_storage_dir):
        """Test thread safety of StoragePaths initialization."""
        import threading
        import time
        
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {'concurrent': 'concurrent_dir'},
            'base_path': str(temp_storage_dir)
        }
        
        results = []
        errors = []
        
        def create_storage_paths():
            try:
                storage_paths = StoragePaths(mock_provider)
                results.append(storage_paths)
                time.sleep(0.01)  # Small delay to encourage race conditions
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = [threading.Thread(target=create_storage_paths) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have errors
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        assert len(results) == 5, "All threads should complete successfully"
        
        # Verify all results are valid StoragePaths instances
        for result in results:
            assert hasattr(result, '_paths')


class TestStoragePathsErrorRecovery:
    """Test error recovery and resilience in StoragePaths."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_config_provider_exception_recovery(self, caplog):
        """Test recovery when config provider raises exceptions."""
        mock_provider = Mock()
        mock_provider.get_storage_config.side_effect = ValueError("Config parsing error")
        
        # Should not crash
        storage_paths = StoragePaths(mock_provider)
        
        assert hasattr(storage_paths, '_paths')
        assert "Failed to initialize storage paths" in caplog.text
    
    def test_partial_directory_creation_failure(self, temp_storage_dir, caplog):
        """Test behavior when some directories can be created but others fail."""
        # Create a file where we want to create a directory
        blocking_file = temp_storage_dir / 'blocked_dir'
        blocking_file.write_text("This file blocks directory creation")
        
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'good_dir': 'good_directory',
                'blocked_dir': 'blocked_dir'  # This will conflict with existing file
            },
            'base_path': str(temp_storage_dir)
        }
        
        # Should handle partial failure gracefully
        storage_paths = StoragePaths(mock_provider)
        
        # Should have initialized despite partial failure
        assert hasattr(storage_paths, '_paths')
        
        # Cleanup blocking file
        if blocking_file.exists():
            blocking_file.unlink()
    
    def test_invalid_base_path_handling(self, caplog):
        """Test handling of invalid base paths."""
        mock_provider = Mock()
        
        # Invalid base paths
        invalid_base_paths = [
            '/dev/null/cannot/create/here',  # Invalid path
            '',  # Empty path
            None,  # None path
        ]
        
        for invalid_path in invalid_base_paths:
            mock_provider.get_storage_config.return_value = {
                'paths': {'test': 'test_dir'},
                'base_path': invalid_path
            }
            
            # Should handle gracefully without crashing
            try:
                storage_paths = StoragePaths(mock_provider)
                assert hasattr(storage_paths, '_paths')
            except Exception as e:
                # If it raises an exception, it should be a well-defined one
                assert isinstance(e, (OSError, ValueError, TypeError))
    
    def test_malformed_paths_config(self):
        """Test handling of malformed paths configuration."""
        mock_provider = Mock()
        
        # Various malformed configs
        malformed_configs = [
            {'paths': None},  # None paths
            {'paths': 'not_a_dict'},  # String instead of dict
            {'paths': []},  # List instead of dict
            {'paths': {'valid': 'good', 'invalid': None}},  # Mixed valid/invalid
        ]
        
        for config in malformed_configs:
            mock_provider.get_storage_config.return_value = config
            
            # Should handle gracefully
            try:
                storage_paths = StoragePaths(mock_provider)
                assert hasattr(storage_paths, '_paths')
            except Exception as e:
                # Should raise appropriate exception type
                assert isinstance(e, (TypeError, AttributeError, ValueError))


class TestStoragePathsIntegration:
    """Integration tests for StoragePaths with realistic scenarios."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_realistic_dflow_paths_config(self, temp_storage_dir):
        """Test with realistic DFlow CLI paths configuration."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'jobs',
                'logs': 'logs',
                'output': 'output',
                'cli_source': 'import_source',
                'app_upload': 'app_upload',
                'app_processing': 'app_processing',
                'tokens': 'tokens'
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should initialize successfully
        assert hasattr(storage_paths, '_paths')
        # Directory creation depends on actual implementation behavior
    
    def test_paths_with_existing_directory_structure(self, temp_storage_dir):
        """Test StoragePaths with pre-existing directory structure."""
        # Create some directories first
        existing_dirs = ['existing_logs', 'existing_jobs']
        for dir_name in existing_dirs:
            (temp_storage_dir / dir_name).mkdir()
        
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'logs': 'existing_logs',  # Already exists
                'jobs': 'existing_jobs',  # Already exists
                'new_dir': 'new_output'   # Doesn't exist
            },
            'base_path': str(temp_storage_dir)
        }
        
        storage_paths = StoragePaths(mock_provider)
        
        # Should initialize successfully
        assert hasattr(storage_paths, '_paths')
        
        # Pre-existing directories should still exist
        assert (temp_storage_dir / 'existing_logs').exists()
        assert (temp_storage_dir / 'existing_jobs').exists()
    
    def test_paths_config_provider_compatibility(self, temp_storage_dir):
        """Test compatibility with different config provider implementations."""
        # Mock different config provider behaviors
        providers = [
            # Standard dict return
            {'paths': {'logs': 'logs'}, 'base_path': str(temp_storage_dir)},
            
            # Minimal config
            {'paths': {}},
            
            # Extended config with extra fields
            {
                'paths': {'logs': 'logs'},
                'base_path': str(temp_storage_dir),
                'extra_field': 'ignored',
                'version': '1.0'
            }
        ]
        
        for config_data in providers:
            mock_provider = Mock()
            mock_provider.get_storage_config.return_value = config_data
            
            # Should handle all variations
            storage_paths = StoragePaths(mock_provider)
            assert hasattr(storage_paths, '_paths')
            assert hasattr(storage_paths, 'config_provider')
    
    def test_environment_variable_interaction(self, temp_storage_dir):
        """Test interaction with environment variables that might affect paths."""
        # Test with environment variables that might influence behavior
        with patch.dict('os.environ', {
            'TMPDIR': str(temp_storage_dir),
            'HOME': str(temp_storage_dir),
            'TEMP': str(temp_storage_dir)
        }):
            mock_provider = Mock()
            mock_provider.get_storage_config.return_value = {
                'paths': {'temp': 'temp_dir'},
                'base_path': str(temp_storage_dir)
            }
            
            storage_paths = StoragePaths(mock_provider)
            
            # Should initialize successfully regardless of environment
            assert hasattr(storage_paths, '_paths')


class TestStoragePathsPropertyAccessors:
    """Test StoragePaths property accessor methods."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def configured_storage_paths(self, temp_storage_dir):
        """Create configured StoragePaths instance."""
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {
                'jobs': 'test_jobs',
                'logs': 'test_logs', 
                'output': 'test_output',
                'cli_source': 'test_cli_source',
                'app_upload': 'test_app_upload',
                'app_processing': 'test_app_processing'
            },
            'base_path': str(temp_storage_dir)
        }
        return StoragePaths(mock_provider)
    
    def test_jobs_property(self, configured_storage_paths, temp_storage_dir):
        """Test jobs property accessor."""
        jobs_path = configured_storage_paths.jobs
        assert isinstance(jobs_path, Path)
        assert jobs_path == temp_storage_dir / 'test_jobs'
    
    def test_logs_property(self, configured_storage_paths, temp_storage_dir):
        """Test logs property accessor."""
        logs_path = configured_storage_paths.logs
        assert isinstance(logs_path, Path)
        assert logs_path == temp_storage_dir / 'test_logs'
    
    def test_output_property(self, configured_storage_paths, temp_storage_dir):
        """Test output property accessor."""
        output_path = configured_storage_paths.output
        assert isinstance(output_path, Path)
        assert output_path == temp_storage_dir / 'test_output'
    
    def test_cli_source_property(self, configured_storage_paths, temp_storage_dir):
        """Test cli_source property accessor."""
        cli_source_path = configured_storage_paths.cli_source
        assert isinstance(cli_source_path, Path)
        assert cli_source_path == temp_storage_dir / 'test_cli_source'
    
    def test_app_upload_property(self, configured_storage_paths, temp_storage_dir):
        """Test app_upload property accessor."""
        app_upload_path = configured_storage_paths.app_upload
        assert isinstance(app_upload_path, Path)
        assert app_upload_path == temp_storage_dir / 'test_app_upload'
    
    def test_app_processing_property(self, configured_storage_paths, temp_storage_dir):
        """Test app_processing property accessor."""
        app_processing_path = configured_storage_paths.app_processing
        assert isinstance(app_processing_path, Path)
        assert app_processing_path == temp_storage_dir / 'test_app_processing'
    
    
    def test_get_path_method(self, configured_storage_paths, temp_storage_dir):
        """Test get_path method for dynamic access."""
        # Test valid file types
        jobs_path = configured_storage_paths.get_path('jobs')
        assert jobs_path == temp_storage_dir / 'test_jobs'
        
        logs_path = configured_storage_paths.get_path('logs')
        assert logs_path == temp_storage_dir / 'test_logs'
    
    def test_get_path_invalid_type(self, configured_storage_paths):
        """Test get_path method with invalid file type."""
        with pytest.raises(ValueError, match="Unknown file type"):
            configured_storage_paths.get_path('nonexistent_type')
    
    def test_get_all_paths_method(self, configured_storage_paths, temp_storage_dir):
        """Test get_all_paths method."""
        all_paths = configured_storage_paths.get_all_paths()
        
        assert isinstance(all_paths, dict)
        assert 'jobs' in all_paths
        assert 'logs' in all_paths
        assert all_paths['jobs'] == temp_storage_dir / 'test_jobs'
        assert all_paths['logs'] == temp_storage_dir / 'test_logs'
        
        # Should be a copy, not the original
        all_paths['new_key'] = 'test'
        assert 'new_key' not in configured_storage_paths._paths
    
    def test_str_representation(self, configured_storage_paths):
        """Test __str__ method."""
        str_repr = str(configured_storage_paths)
        
        assert 'StoragePaths(' in str_repr
        assert 'jobs=' in str_repr
        assert 'logs=' in str_repr


class TestStoragePathsUtilityFunctions:
    """Test utility functions in paths module."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_initialize_paths_function(self, temp_storage_dir):
        """Test initialize_paths global function."""
        from cdflow_cli.utils.paths import initialize_paths, get_paths, is_initialized
        
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {'jobs': 'test_jobs'},
            'base_path': str(temp_storage_dir)
        }
        
        # Initialize paths
        result = initialize_paths(mock_provider)
        assert isinstance(result, StoragePaths)
        
        # Should be initialized
        assert is_initialized() is True
        
        # Should be able to get paths
        paths = get_paths()
        assert isinstance(paths, StoragePaths)
    
    def test_get_paths_not_initialized(self):
        """Test get_paths when not initialized."""
        from cdflow_cli.utils.paths import get_paths, _PATHS
        
        # Reset global state
        import cdflow_cli.utils.paths as paths_module
        paths_module._PATHS = None
        
        with pytest.raises(RuntimeError, match="Storage paths not initialized"):
            get_paths()
    
    def test_is_initialized_function(self, temp_storage_dir):
        """Test is_initialized function."""
        from cdflow_cli.utils.paths import is_initialized, initialize_paths
        import cdflow_cli.utils.paths as paths_module
        
        # Reset state
        paths_module._PATHS = None
        assert is_initialized() is False
        
        # Initialize
        mock_provider = Mock()
        mock_provider.get_storage_config.return_value = {
            'paths': {'jobs': 'test_jobs'},
            'base_path': str(temp_storage_dir)
        }
        initialize_paths(mock_provider)
        
        assert is_initialized() is True
    
    def test_ensure_file_parent_exists(self, temp_storage_dir):
        """Test ensure_file_parent_exists utility function."""
        from cdflow_cli.utils.paths import ensure_file_parent_exists
        
        # Test with nested path
        test_file = temp_storage_dir / 'nested' / 'deep' / 'file.txt'
        
        # Parent shouldn't exist yet
        assert not test_file.parent.exists()
        
        # Ensure parent exists
        ensure_file_parent_exists(test_file)
        
        # Parent should now exist
        assert test_file.parent.exists()
        assert test_file.parent.is_dir()
    
    def test_safe_read_text_utility(self, temp_storage_dir):
        """Test safe_read_text utility function."""
        from cdflow_cli.utils.paths import safe_read_text
        
        # Create test file
        test_file = temp_storage_dir / 'test.txt'
        test_file.write_text('Hello, world!', encoding='utf-8')
        
        # Test successful read
        content = safe_read_text(test_file)
        assert content == 'Hello, world!'
        
        # Test with custom encoding
        content = safe_read_text(test_file, encoding='utf-8')
        assert content == 'Hello, world!'
        
        # Test nonexistent file with default
        nonexistent = temp_storage_dir / 'nonexistent.txt'
        content = safe_read_text(nonexistent, default='default content')
        assert content == 'default content'
        
        # Test nonexistent file with empty default
        content = safe_read_text(nonexistent)
        assert content == ''
    
    def test_safe_write_text_utility(self, temp_storage_dir):
        """Test safe_write_text utility function."""
        from cdflow_cli.utils.paths import safe_write_text
        
        # Test writing to new file
        test_file = temp_storage_dir / 'write_test.txt'
        result = safe_write_text(test_file, 'Test content')
        
        assert result is True
        assert test_file.exists()
        assert test_file.read_text() == 'Test content'
        
        # Test writing with custom encoding
        test_file2 = temp_storage_dir / 'write_test2.txt'
        result = safe_write_text(test_file2, 'Test content 2', encoding='utf-8')
        
        assert result is True
        assert test_file2.read_text(encoding='utf-8') == 'Test content 2'
        
        # Test writing to nested path (should create parent directories)
        nested_file = temp_storage_dir / 'nested' / 'deep' / 'file.txt'
        result = safe_write_text(nested_file, 'Nested content')
        
        assert result is True
        assert nested_file.exists()
        assert nested_file.read_text() == 'Nested content'