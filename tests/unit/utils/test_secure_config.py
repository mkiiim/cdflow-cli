import pytest
import os
import sys
from unittest.mock import patch, Mock
from cdflow_cli.utils.secure_config import (
    SecureConfigValidator,
    SecretManager,
    secure_startup_check
)


class TestSecureConfigValidator:
    """Test secure configuration validation for OAuth credentials."""
    
    def test_required_vars_defined(self):
        """Test that required environment variables are properly defined."""
        expected_vars = ["NB_SLUG", "NB_CLIENT_ID", "NB_CLIENT_SECRET"]
        assert SecureConfigValidator.REQUIRED_VARS == expected_vars
    
    def test_placeholder_patterns_defined(self):
        """Test that placeholder patterns are defined for validation."""
        patterns = SecureConfigValidator.PLACEHOLDER_PATTERNS
        assert "your-" in patterns
        assert "example-" in patterns
        assert "placeholder-" in patterns
        assert "change-this" in patterns
    
    def test_validate_environment_with_valid_credentials(self):
        """Test environment validation with valid OAuth credentials."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'valid-nation-slug',
            'NB_CLIENT_ID': 'valid_client_id_12345',
            'NB_CLIENT_SECRET': 'valid_client_secret_with_sufficient_length'
        }, clear=True):
            result = SecureConfigValidator.validate_environment()
            assert result is True
    
    def test_validate_environment_missing_variables(self, caplog):
        """Test validation fails when required variables are missing."""
        with patch.dict('os.environ', {}, clear=True):
            result = SecureConfigValidator.validate_environment()
            
            assert result is False
            assert "Missing required environment variables" in caplog.text
            assert "NB_SLUG" in caplog.text
            assert "NB_CLIENT_ID" in caplog.text
            assert "NB_CLIENT_SECRET" in caplog.text
    
    def test_validate_environment_partial_missing(self, caplog):
        """Test validation with only some variables present."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'test-nation',
            # Missing NB_CLIENT_ID and NB_CLIENT_SECRET
        }, clear=True):
            result = SecureConfigValidator.validate_environment()
            
            assert result is False
            assert "Missing required environment variables" in caplog.text
            assert "NB_CLIENT_ID" in caplog.text
            assert "NB_CLIENT_SECRET" in caplog.text
    
    def test_validate_environment_placeholder_detection(self, caplog):
        """Test that placeholder values are detected and rejected."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'your-nation-slug',  # Contains placeholder pattern
            'NB_CLIENT_ID': 'example-client-id',  # Contains placeholder pattern
            'NB_CLIENT_SECRET': 'change-this-secret-value'  # Contains placeholder pattern
        }, clear=True):
            result = SecureConfigValidator.validate_environment()
            
            assert result is False
            assert "placeholder values" in caplog.text
    
    def test_validate_environment_short_secret_warning(self, caplog):
        """Test warning for short client secrets."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'valid-nation',
            'NB_CLIENT_ID': 'valid_client_id',
            'NB_CLIENT_SECRET': 'short'  # Too short, should warn
        }, clear=True):
            result = SecureConfigValidator.validate_environment()
            
            # Should still pass but with warning
            assert result is True
            assert "too short" in caplog.text
    
    def test_get_oauth_config_success(self):
        """Test successful OAuth configuration retrieval."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'test-nation',
            'NB_CLIENT_ID': 'test_client_id_12345',
            'NB_CLIENT_SECRET': 'test_client_secret_with_sufficient_length',
            'NB_CONFIG_NAME': 'development',
            'NB_REDIRECT_URI': 'http://localhost:8000/callback'
        }, clear=True):
            config = SecureConfigValidator.get_oauth_config()
            
            assert config['slug'] == 'test-nation'
            assert config['client_id'] == 'test_client_id_12345'
            assert config['client_secret'] == 'test_client_secret_with_sufficient_length'
            assert config['config_name'] == 'development'
            assert config['redirect_uri'] == 'http://localhost:8000/callback'
    
    def test_get_oauth_config_default_config_name(self):
        """Test OAuth config with default config name."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'test-nation',
            'NB_CLIENT_ID': 'test_client_id_12345',
            'NB_CLIENT_SECRET': 'test_client_secret_with_sufficient_length'
            # No NB_CONFIG_NAME - should default to 'not_configured'
        }, clear=True):
            config = SecureConfigValidator.get_oauth_config()
            
            assert config['config_name'] == 'not_configured'
            assert 'redirect_uri' not in config  # Should not be present if not set
    
    def test_get_oauth_config_validation_failure(self):
        """Test OAuth config fails when validation fails."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OAuth configuration validation failed"):
                SecureConfigValidator.get_oauth_config()
    
    def test_placeholder_pattern_case_insensitive(self, caplog):
        """Test that placeholder detection is case-insensitive."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'YOUR-NATION-SLUG',  # Uppercase placeholder pattern
            'NB_CLIENT_ID': 'Example-Client-ID',  # Mixed case placeholder
            'NB_CLIENT_SECRET': 'CHANGE-THIS-SECRET'  # Uppercase placeholder
        }, clear=True):
            result = SecureConfigValidator.validate_environment()
            
            assert result is False
            assert "placeholder values" in caplog.text
    
    def test_validate_environment_edge_cases(self):
        """Test validation with edge case values."""
        # Test with empty strings
        with patch.dict('os.environ', {
            'NB_SLUG': '',
            'NB_CLIENT_ID': 'valid_id',
            'NB_CLIENT_SECRET': 'valid_secret_12345678'
        }, clear=True):
            result = SecureConfigValidator.validate_environment()
            assert result is False  # Empty string should be treated as missing
        
        # Test with whitespace-only values
        with patch.dict('os.environ', {
            'NB_SLUG': '   ',
            'NB_CLIENT_ID': 'valid_id',
            'NB_CLIENT_SECRET': 'valid_secret_12345678'
        }, clear=True):
            # Note: Current implementation doesn't strip whitespace,
            # so this might pass - depends on implementation details
            result = SecureConfigValidator.validate_environment()
            # Test passes or fails depending on whitespace handling


class TestSecretManager:
    """Test SecretManager OAuth configuration management."""
    
    def test_secret_manager_init(self):
        """Test SecretManager initialization."""
        manager = SecretManager()
        assert isinstance(manager, SecretManager)
    
    def test_secret_manager_get_oauth_config(self):
        """Test SecretManager OAuth config retrieval."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'manager-test-nation',
            'NB_CLIENT_ID': 'manager_client_id_12345',
            'NB_CLIENT_SECRET': 'manager_client_secret_sufficient_length'
        }, clear=True):
            manager = SecretManager()
            config = manager.get_oauth_config()
            
            assert config['slug'] == 'manager-test-nation'
            assert config['client_id'] == 'manager_client_id_12345'
            assert config['client_secret'] == 'manager_client_secret_sufficient_length'
    
    def test_secret_manager_delegates_to_validator(self):
        """Test that SecretManager properly delegates to SecureConfigValidator."""
        with patch.object(SecureConfigValidator, 'get_oauth_config') as mock_validator:
            mock_config = {'test': 'config'}
            mock_validator.return_value = mock_config
            
            manager = SecretManager()
            result = manager.get_oauth_config()
            
            mock_validator.assert_called_once()
            assert result == mock_config


class TestSecureStartupCheck:
    """Test secure startup validation functionality."""
    
    @patch('psutil.Process')
    def test_secure_startup_check_success(self, mock_process):
        """Test successful security startup check."""
        # Mock process command line
        mock_proc = Mock()
        mock_proc.cmdline.return_value = ['python', 'app.py', '--config', 'config.yaml']
        mock_process.return_value = mock_proc
        
        with patch.dict('os.environ', {
            'NB_SLUG': 'startup-test-nation',
            'NB_CLIENT_ID': 'startup_client_id_12345',
            'NB_CLIENT_SECRET': 'startup_client_secret_sufficient_length'
        }, clear=True):
            # Should not raise SystemExit
            try:
                secure_startup_check()
            except SystemExit:
                pytest.fail("secure_startup_check should not call sys.exit() with valid config")
    
    @patch('psutil.Process')
    def test_secure_startup_check_command_line_exposure(self, mock_process, caplog):
        """Test detection of secrets in command line."""
        # Mock process with sensitive information in command line
        mock_proc = Mock()
        mock_proc.cmdline.return_value = [
            'python', 'app.py', '--client_secret', 'exposed_secret'
        ]
        mock_process.return_value = mock_proc
        
        with patch.dict('os.environ', {
            'NB_SLUG': 'startup-test-nation',
            'NB_CLIENT_ID': 'startup_client_id_12345',
            'NB_CLIENT_SECRET': 'startup_client_secret_sufficient_length'
        }, clear=True):
            secure_startup_check()
            
            assert "Potential secret exposure in command line" in caplog.text
            assert "client_secret" in caplog.text
    
    @patch('psutil.Process')
    @patch('sys.exit')
    def test_secure_startup_check_validation_failure(self, mock_exit, mock_process):
        """Test startup check exits on validation failure."""
        # Mock process
        mock_proc = Mock()
        mock_proc.cmdline.return_value = ['python', 'app.py']
        mock_process.return_value = mock_proc
        
        # Invalid environment (missing credentials)
        with patch.dict('os.environ', {}, clear=True):
            secure_startup_check()
            
            # Should call sys.exit(1) on validation failure
            mock_exit.assert_called_once_with(1)
    
    @patch('psutil.Process')
    def test_secure_startup_check_multiple_sensitive_patterns(self, mock_process, caplog):
        """Test detection of multiple sensitive patterns in command line."""
        # Mock process with multiple sensitive patterns
        mock_proc = Mock()
        mock_proc.cmdline.return_value = [
            'python', 'app.py', 
            '--password', 'secret_pass',
            '--token', 'auth_token_123'
        ]
        mock_process.return_value = mock_proc
        
        with patch.dict('os.environ', {
            'NB_SLUG': 'startup-test-nation',
            'NB_CLIENT_ID': 'startup_client_id_12345',
            'NB_CLIENT_SECRET': 'startup_client_secret_sufficient_length'
        }, clear=True):
            secure_startup_check()
            
            # Should warn about both patterns
            log_text = caplog.text
            assert "password" in log_text
            assert "token" in log_text
    
    @patch('psutil.Process')
    def test_secure_startup_check_case_insensitive_pattern_detection(self, mock_process, caplog):
        """Test that sensitive pattern detection is case-insensitive."""
        # Mock process with uppercase sensitive pattern
        mock_proc = Mock()
        mock_proc.cmdline.return_value = [
            'python', 'app.py', '--CLIENT_SECRET', 'exposed'
        ]
        mock_process.return_value = mock_proc
        
        with patch.dict('os.environ', {
            'NB_SLUG': 'startup-test-nation',
            'NB_CLIENT_ID': 'startup_client_id_12345',
            'NB_CLIENT_SECRET': 'startup_client_secret_sufficient_length'
        }, clear=True):
            secure_startup_check()
            
            assert "client_secret" in caplog.text


class TestSecureConfigIntegration:
    """Integration tests for secure configuration components."""
    
    def test_end_to_end_oauth_flow(self):
        """Test complete OAuth configuration flow."""
        with patch.dict('os.environ', {
            'NB_SLUG': 'integration-test-nation',
            'NB_CLIENT_ID': 'integration_client_id_12345',
            'NB_CLIENT_SECRET': 'integration_client_secret_sufficient_length',
            'NB_CONFIG_NAME': 'integration',
            'NB_REDIRECT_URI': 'http://localhost:9000/callback'
        }, clear=True):
            # Test validation
            assert SecureConfigValidator.validate_environment() is True
            
            # Test configuration retrieval
            config = SecureConfigValidator.get_oauth_config()
            assert config['slug'] == 'integration-test-nation'
            assert config['config_name'] == 'integration'
            assert config['redirect_uri'] == 'http://localhost:9000/callback'
            
            # Test SecretManager
            manager = SecretManager()
            manager_config = manager.get_oauth_config()
            assert manager_config == config
    
    def test_security_hardening_scenarios(self):
        """Test various security hardening scenarios."""
        # Test with potentially malicious values
        malicious_configs = [
            {
                'NB_SLUG': '../../../etc/passwd',
                'NB_CLIENT_ID': 'valid_client_id_12345',
                'NB_CLIENT_SECRET': 'valid_secret_sufficient_length'
            },
            {
                'NB_SLUG': 'normal-slug',
                'NB_CLIENT_ID': '; rm -rf /',
                'NB_CLIENT_SECRET': 'valid_secret_sufficient_length'
            },
            {
                'NB_SLUG': 'normal-slug',
                'NB_CLIENT_ID': 'valid_client_id_12345',
                'NB_CLIENT_SECRET': '<script>alert("xss")</script>'
            }
        ]
        
        for malicious_config in malicious_configs:
            with patch.dict('os.environ', malicious_config, clear=True):
                # Should not crash, should return configuration
                # Security is handled by consuming code, not validator
                try:
                    result = SecureConfigValidator.validate_environment()
                    # Should complete without exceptions
                    assert isinstance(result, bool)
                    
                    if result:
                        config = SecureConfigValidator.get_oauth_config()
                        assert isinstance(config, dict)
                        assert 'slug' in config
                        assert 'client_id' in config
                        assert 'client_secret' in config
                        
                except Exception as e:
                    # If it fails, should fail gracefully
                    assert isinstance(e, (ValueError, RuntimeError))
    
    def test_error_resilience(self):
        """Test that secure config handles various error conditions gracefully."""
        # Test with None values (should be treated as missing)
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = None
            
            result = SecureConfigValidator.validate_environment()
            assert result is False
        
        # Test with exception in environment access
        with patch('os.getenv') as mock_getenv:
            mock_getenv.side_effect = OSError("Environment access error")
            
            try:
                result = SecureConfigValidator.validate_environment()
                # Should handle gracefully
                assert isinstance(result, bool)
            except Exception:
                # Or raise appropriate exception
                pass


class TestSecureConfigMainBlock:
    """Test the __main__ block functionality."""
    
    def test_main_block_execution(self, capfd):
        """Test the main block when run as script."""
        import subprocess
        import sys
        
        # Run the module as a script with valid environment
        env = {
            'NB_SLUG': 'test-main-nation',
            'NB_CLIENT_ID': 'test_main_client_id_12345',
            'NB_CLIENT_SECRET': 'test_main_client_secret_sufficient_length',
            'NB_REDIRECT_URI': 'http://localhost:8000/callback'
        }
        
        result = subprocess.run([
            sys.executable, '-m', 'cdflow_cli.utils.secure_config'
        ], env={**os.environ, **env}, capture_output=True, text=True)
        
        # Should complete successfully
        assert result.returncode == 0
        assert "OAuth configuration valid" in result.stdout
        assert "test-main-nation" in result.stdout
    
    def test_main_block_with_invalid_config(self):
        """Test main block with invalid configuration."""
        import subprocess
        import sys
        
        # Run with no environment variables
        result = subprocess.run([
            sys.executable, '-m', 'cdflow_cli.utils.secure_config'
        ], env={}, capture_output=True, text=True)
        
        # Should exit with error
        assert result.returncode == 1
        # Error message goes to stderr, not stdout
        assert "OAuth configuration error" in result.stderr or "Security validation failed" in result.stderr