import pytest
import subprocess
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCLIWorkflows:
    """Integration tests for CLI workflows."""
    
    @pytest.fixture
    def temp_workspace(self, temp_dir):
        """Create a temporary workspace for integration tests."""
        workspace = temp_dir / 'workspace'
        workspace.mkdir()
        
        # Create config directory
        config_dir = workspace / '.config' / 'cdflow'
        config_dir.mkdir(parents=True)
        
        return workspace
    
    @pytest.fixture
    def sample_config_file(self, temp_workspace):
        """Create a sample configuration file."""
        config_data = {
            'nationbuilder': {
                'slug': 'test-nation',
                'client_id': 'test-client-id',
                'client_secret': 'test-client-secret',
                'redirect_uri': 'http://localhost:8000/callback',
                'oauth': {
                    'port': 8000,
                    'timeout': 120
                }
            },
            'import': {
                'source': {
                    'type': 'canadahelps',
                    'file_path': 'donations.csv'
                },
                'processing': {
                    'batch_size': 5,
                    'rate_limit': 60,
                    'dry_run': True
                }
            },
            'logging': {
                'level': 'INFO'
            }
        }
        
        config_file = temp_workspace / 'config.yaml'
        config_file.write_text(yaml.dump(config_data))
        return config_file
    
    @pytest.fixture
    def sample_csv_file(self, temp_workspace, sample_canadahelps_data):
        """Create a sample CSV file."""
        csv_file = temp_workspace / 'donations.csv'
        csv_file.write_text(sample_canadahelps_data)
        return csv_file
    
    def test_init_command_workflow(self, temp_workspace):
        """Test the init command workflow."""
        with patch('cdflow_cli.cli.commands_init.create_config_file', return_value=True):
            with patch('cdflow_cli.cli.commands_init.create_oauth_file', return_value=True):
                with patch('cdflow_cli.cli.commands_init.deploy_logos', return_value=True):
                    # Run init command
                    result = subprocess.run([
                        'python', '-m', 'cdflow_cli.cli.main', 
                        'init', '--config-dir', str(temp_workspace / '.config' / 'cdflow')
                    ], capture_output=True, text=True, cwd=temp_workspace)
                    
                    assert result.returncode == 0
    
    @patch('cdflow_cli.services.import_service.DonationImportService')
    def test_import_command_workflow(self, mock_service_class, temp_workspace, sample_config_file, sample_csv_file):
        """Test the import command workflow."""
        # Mock the import service
        mock_service = MagicMock()
        mock_service.run.return_value = {'status': 'success', 'imported': 3}
        mock_service_class.return_value = mock_service
        
        with patch('cdflow_cli.utils.config.ConfigProvider') as mock_config_provider:
            mock_provider = MagicMock()
            mock_config_provider.return_value = mock_provider
            
            result = subprocess.run([
                'python', '-m', 'cdflow_cli.cli.main',
                'import', '--config', str(sample_config_file)
            ], capture_output=True, text=True, cwd=temp_workspace)
            
            assert result.returncode == 0
            mock_service.run.assert_called_once()
    
    @patch('cdflow_cli.services.rollback_service.DonationRollbackService')
    def test_rollback_command_workflow(self, mock_service_class, temp_workspace, sample_config_file):
        """Test the rollback command workflow."""
        # Add rollback config to the config file
        with open(sample_config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        config['rollback'] = {
            'job_id': 'test-job-123',
            'confirm_deletion': False
        }
        
        with open(sample_config_file, 'w') as f:
            yaml.dump(config, f)
        
        # Mock the rollback service
        mock_service = MagicMock()
        mock_service.run.return_value = {'status': 'success', 'rolled_back': 2}
        mock_service_class.return_value = mock_service
        
        with patch('cdflow_cli.utils.config.ConfigProvider') as mock_config_provider:
            mock_provider = MagicMock()
            mock_config_provider.return_value = mock_provider
            
            result = subprocess.run([
                'python', '-m', 'cdflow_cli.cli.main',
                'rollback', '--config', str(sample_config_file)
            ], capture_output=True, text=True, cwd=temp_workspace)
            
            assert result.returncode == 0
            mock_service.run.assert_called_once()
    
    def test_version_command(self, temp_workspace):
        """Test the version command."""
        result = subprocess.run([
            'python', '-m', 'cdflow_cli.cli.main', '--version'
        ], capture_output=True, text=True, cwd=temp_workspace)
        
        assert result.returncode == 0
        assert 'cdflow' in result.stdout
    
    def test_help_command(self, temp_workspace):
        """Test the help command."""
        result = subprocess.run([
            'python', '-m', 'cdflow_cli.cli.main', '--help'
        ], capture_output=True, text=True, cwd=temp_workspace)
        
        assert result.returncode == 0
        assert 'DonationFlow CLI' in result.stdout
        assert 'init' in result.stdout
        assert 'import' in result.stdout
        assert 'rollback' in result.stdout
    
    def test_import_with_type_and_file_override(self, temp_workspace, sample_config_file, sample_csv_file):
        """Test import with type and file overrides."""
        with patch('cdflow_cli.services.import_service.DonationImportService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.run.return_value = {'status': 'success'}
            mock_service_class.return_value = mock_service
            
            with patch('cdflow_cli.utils.config.ConfigProvider') as mock_config_provider:
                mock_provider = MagicMock()
                mock_config_provider.return_value = mock_provider
                
                result = subprocess.run([
                    'python', '-m', 'cdflow_cli.cli.main',
                    'import', 
                    '--config', str(sample_config_file),
                    '--type', 'paypal',
                    '--file', str(sample_csv_file)
                ], capture_output=True, text=True, cwd=temp_workspace)
                
                assert result.returncode == 0
    
    def test_invalid_config_file(self, temp_workspace):
        """Test handling of invalid config file."""
        result = subprocess.run([
            'python', '-m', 'cdflow_cli.cli.main',
            'import', '--config', 'nonexistent.yaml'
        ], capture_output=True, text=True, cwd=temp_workspace)
        
        assert result.returncode != 0
        assert 'error' in result.stderr.lower() or 'not found' in result.stderr.lower()
    
    def test_import_type_file_validation_error(self, temp_workspace, sample_config_file):
        """Test validation error when --type is used without --file."""
        result = subprocess.run([
            'python', '-m', 'cdflow_cli.cli.main',
            'import', 
            '--config', str(sample_config_file),
            '--type', 'canadahelps'
            # Missing --file argument
        ], capture_output=True, text=True, cwd=temp_workspace)
        
        assert result.returncode != 0
        assert 'must be used together' in result.stderr
    
    def test_no_command_shows_help(self, temp_workspace):
        """Test that running without command shows help."""
        result = subprocess.run([
            'python', '-m', 'cdflow_cli.cli.main'
        ], capture_output=True, text=True, cwd=temp_workspace)
        
        assert result.returncode != 0
        # Should show help output
        assert 'usage:' in result.stderr or 'usage:' in result.stdout
    
    @patch('cdflow_cli.services.import_service.DonationImportService')
    def test_debug_logging_level(self, mock_service_class, temp_workspace, sample_config_file):
        """Test import with debug logging level."""
        mock_service = MagicMock()
        mock_service.run.return_value = {'status': 'success'}
        mock_service_class.return_value = mock_service
        
        with patch('cdflow_cli.utils.config.ConfigProvider') as mock_config_provider:
            with patch('cdflow_cli.utils.logging.setup_logging') as mock_setup_logging:
                mock_provider = MagicMock()
                mock_config_provider.return_value = mock_provider
                
                result = subprocess.run([
                    'python', '-m', 'cdflow_cli.cli.main',
                    'import', 
                    '--config', str(sample_config_file),
                    '--log-level', 'DEBUG'
                ], capture_output=True, text=True, cwd=temp_workspace)
                
                assert result.returncode == 0
                # Verify debug logging was set up
                mock_setup_logging.assert_called_with('DEBUG')


class TestEndToEndWorkflows:
    """End-to-end workflow tests with minimal mocking."""
    
    def test_init_creates_config_files(self, temp_workspace):
        """Test that init actually creates configuration files."""
        config_dir = temp_workspace / '.config' / 'cdflow'
        
        with patch('cdflow_cli.cli.commands_init.get_template_content') as mock_get_template:
            mock_get_template.return_value = "test config content"
            
            with patch('cdflow_cli.cli.commands_init.get_oauth_template_content') as mock_get_oauth:
                mock_get_oauth.return_value = "test oauth content"
                
                with patch('cdflow_cli.cli.commands_init.deploy_logos'):
                    result = subprocess.run([
                        'python', '-m', 'cdflow_cli.cli.main',
                        'init', '--config-dir', str(config_dir)
                    ], capture_output=True, text=True, cwd=temp_workspace)
                    
                    assert result.returncode == 0
                    
                    # Verify files were created
                    assert (config_dir / 'config.yaml').exists()
                    assert (config_dir / 'nb_local.env').exists()
    
    def test_config_validation_workflow(self, temp_workspace):
        """Test configuration validation in real workflow."""
        # Create invalid config
        invalid_config = {
            'nationbuilder': {
                # Missing required fields
                'slug': 'test'
            }
        }
        
        config_file = temp_workspace / 'invalid_config.yaml'
        config_file.write_text(yaml.dump(invalid_config))
        
        result = subprocess.run([
            'python', '-m', 'cdflow_cli.cli.main',
            'import', '--config', str(config_file)
        ], capture_output=True, text=True, cwd=temp_workspace)
        
        assert result.returncode != 0