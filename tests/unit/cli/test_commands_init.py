"""
Working tests for cdflow_cli.cli.commands_init module.
Simplified version focusing on core functionality testing.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from cdflow_cli.cli.commands_init import (
    get_template_content,
    get_oauth_template_content,
    check_file_conflicts,
    copy_template_file,
    copy_oauth_template_file,
    run_init,
    main
)


class TestGetTemplateContent:
    """Test the get_template_content function."""
    
    def test_get_template_content_with_importlib_resources(self):
        """Test template retrieval with importlib.resources."""
        with patch('cdflow_cli.cli.commands_init._has_importlib_resources', True):
            mock_files = MagicMock()
            mock_files.joinpath.return_value.read_text.return_value = "template content"
            
            with patch('cdflow_cli.cli.commands_init.importlib_resources.files', return_value=mock_files):
                result = get_template_content("test.yaml")
                assert result == "template content"
                mock_files.joinpath.assert_called_once_with("test.yaml")
    
    def test_get_template_content_importlib_exception(self):
        """Test exception handling when importlib resources fail."""
        with patch('cdflow_cli.cli.commands_init._has_importlib_resources', True):
            with patch('cdflow_cli.cli.commands_init.importlib_resources.files', side_effect=Exception("Import error")):
                with pytest.raises(FileNotFoundError, match="Template 'test.yaml' not found in package"):
                    get_template_content("test.yaml")
    
    def test_get_template_content_file_not_found_filesystem(self):
        """Test FileNotFoundError when template doesn't exist in filesystem."""
        with patch('cdflow_cli.cli.commands_init._has_importlib_resources', False):
            with patch('cdflow_cli.cli.commands_init._has_pkg_resources', False):
                with pytest.raises(FileNotFoundError, match="Template 'nonexistent.yaml' not found"):
                    get_template_content("nonexistent.yaml")


class TestGetOAuthTemplateContent:
    """Test the get_oauth_template_content function."""
    
    def test_get_oauth_template_content_with_importlib_resources(self):
        """Test OAuth template retrieval with importlib.resources."""
        with patch('cdflow_cli.cli.commands_init._has_importlib_resources', True):
            mock_files = MagicMock()
            mock_files.joinpath.return_value.read_text.return_value = "oauth content"
            
            with patch('cdflow_cli.cli.commands_init.importlib_resources.files', return_value=mock_files):
                result = get_oauth_template_content("nb_local.env")
                assert result == "oauth content"
                mock_files.joinpath.assert_called_once_with("nb_local.env")
    
    def test_get_oauth_template_content_file_not_found(self):
        """Test FileNotFoundError for OAuth template."""
        with patch('cdflow_cli.cli.commands_init._has_importlib_resources', True):
            with patch('cdflow_cli.cli.commands_init.importlib_resources.files', side_effect=Exception("Not found")):
                with pytest.raises(FileNotFoundError, match="OAuth template 'missing.env' not found in package"):
                    get_oauth_template_content("missing.env")


class TestCheckFileConflicts:
    """Test the check_file_conflicts function."""
    
    def test_check_file_conflicts_no_conflicts(self):
        """Test when no files exist (no conflicts)."""
        mock_output_dir = MagicMock()
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_output_dir.__truediv__ = MagicMock(return_value=mock_file)
        
        result = check_file_conflicts(mock_output_dir, ["config.yaml", "template.yaml"])
        assert result == []
    
    def test_check_file_conflicts_with_conflicts(self):
        """Test when some files exist (conflicts detected)."""
        mock_output_dir = MagicMock()
        
        # Mock one existing file, one missing file
        mock_existing = MagicMock()
        mock_existing.exists.return_value = True
        mock_missing = MagicMock()
        mock_missing.exists.return_value = False
        
        # Return different mocks based on filename
        def side_effect(filename):
            return mock_existing if filename == "existing.yaml" else mock_missing
        
        mock_output_dir.__truediv__.side_effect = side_effect
        
        result = check_file_conflicts(mock_output_dir, ["existing.yaml", "missing.yaml"])
        assert len(result) == 1
        assert result[0] == mock_existing


class TestCopyTemplateFile:
    """Test the copy_template_file function."""
    
    @patch('cdflow_cli.cli.commands_init.get_template_content')
    @patch('builtins.print')
    def test_copy_template_file_success_new_file(self, mock_print, mock_get_template):
        """Test successfully copying template to new location."""
        mock_get_template.return_value = "template content"
        
        mock_output_path = MagicMock()
        mock_output_path.exists.return_value = False
        
        result = copy_template_file("test.yaml", mock_output_path, False)
        
        assert result is True
        mock_get_template.assert_called_once_with("test.yaml")
        mock_output_path.write_text.assert_called_once_with("template content")
    
    @patch('cdflow_cli.cli.commands_init.get_template_content')
    @patch('builtins.print')
    def test_copy_template_file_skip_existing(self, mock_print, mock_get_template):
        """Test skipping existing file when force_overwrite is False."""
        mock_output_path = MagicMock()
        mock_output_path.exists.return_value = True
        
        result = copy_template_file("test.yaml", mock_output_path, False)
        
        assert result is False
        mock_get_template.assert_not_called()
        mock_output_path.write_text.assert_not_called()
    
    @patch('cdflow_cli.cli.commands_init.get_template_content')
    @patch('builtins.print')
    def test_copy_template_file_force_overwrite(self, mock_print, mock_get_template):
        """Test force overwriting existing file."""
        mock_get_template.return_value = "new content"
        
        mock_output_path = MagicMock()
        mock_output_path.exists.return_value = True
        
        result = copy_template_file("test.yaml", mock_output_path, True)
        
        assert result is True
        mock_get_template.assert_called_once_with("test.yaml")
        mock_output_path.write_text.assert_called_once_with("new content")
    
    @patch('cdflow_cli.cli.commands_init.get_template_content')
    @patch('builtins.print')
    def test_copy_template_file_exception_handling(self, mock_print, mock_get_template):
        """Test exception handling when template copy fails."""
        mock_get_template.side_effect = Exception("Template not found")
        
        mock_output_path = MagicMock()
        mock_output_path.exists.return_value = False
        
        result = copy_template_file("missing.yaml", mock_output_path, False)
        
        assert result is False
        mock_print.assert_called()


class TestCopyOAuthTemplateFile:
    """Test the copy_oauth_template_file function."""
    
    @patch('cdflow_cli.cli.commands_init.get_oauth_template_content')
    @patch('builtins.print')
    def test_copy_oauth_template_file_success(self, mock_print, mock_get_oauth):
        """Test successfully copying OAuth template."""
        mock_get_oauth.return_value = "oauth content"
        
        mock_output_path = MagicMock()
        mock_output_path.exists.return_value = False
        
        result = copy_oauth_template_file("nb_local.env", mock_output_path, False)
        
        assert result is True
        mock_get_oauth.assert_called_once_with("nb_local.env")
        mock_output_path.write_text.assert_called_once_with("oauth content")
    
    @patch('cdflow_cli.cli.commands_init.get_oauth_template_content')
    @patch('builtins.print')
    def test_copy_oauth_template_file_skip_existing(self, mock_print, mock_get_oauth):
        """Test skipping existing OAuth file."""
        mock_output_path = MagicMock()
        mock_output_path.exists.return_value = True
        
        result = copy_oauth_template_file("nb_local.env", mock_output_path, False)
        
        assert result is False
        mock_get_oauth.assert_not_called()


class TestRunInit:
    """Test the run_init function."""
    
    @patch('cdflow_cli.cli.commands_init.check_file_conflicts')
    @patch('cdflow_cli.cli.commands_init.copy_template_file')
    @patch('cdflow_cli.cli.commands_init.copy_oauth_template_file')
    @patch('builtins.print')
    def test_run_init_success_new_directory(self, mock_print, mock_copy_oauth, mock_copy_template, mock_check_conflicts):
        """Test successful initialization in new directory."""
        mock_check_conflicts.return_value = []  # No conflicts
        mock_copy_template.return_value = True  # Template copied successfully
        mock_copy_oauth.return_value = True     # OAuth copied successfully
        
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path.resolve.return_value = mock_path
        mock_path.mkdir = MagicMock()
        mock_path.is_dir.return_value = True
        mock_path.expanduser.return_value.exists.return_value = True
        
        mock_env_path = MagicMock()
        mock_env_path.mkdir = MagicMock()
        
        with patch('cdflow_cli.cli.commands_init.Path') as mock_path_class:
            mock_path_class.return_value = mock_path
            mock_path_class.home.return_value = MagicMock()
            mock_path_class.home.return_value.__truediv__ = MagicMock(return_value=mock_env_path)
            
            result = run_init(output_dir="/new/config", force=False, org_logo_path=None)
            
            assert result == 0
            mock_path.mkdir.assert_called_once()
            mock_copy_template.assert_called()
            mock_copy_oauth.assert_called()
    
    @patch('builtins.print')
    def test_run_init_cannot_create_directory(self, mock_print):
        """Test initialization failure when directory cannot be created."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path.resolve.return_value = mock_path
        mock_path.mkdir.side_effect = Exception("Permission denied")
        
        with patch('cdflow_cli.cli.commands_init.Path', return_value=mock_path):
            result = run_init(output_dir="/restricted/path", force=False, org_logo_path=None)
            
            assert result == 1
    
    @patch('builtins.print')
    def test_run_init_path_not_directory(self, mock_print):
        """Test initialization failure when path is not a directory."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.resolve.return_value = mock_path
        mock_path.is_dir.return_value = False
        
        with patch('cdflow_cli.cli.commands_init.Path', return_value=mock_path):
            result = run_init(output_dir="/path/to/file.txt", force=False, org_logo_path=None)
            
            assert result == 1


class TestMain:
    """Test the main function with argument parsing."""
    
    @patch('cdflow_cli.cli.commands_init.run_init')
    def test_main_with_default_config_dir(self, mock_run_init):
        """Test main function with default config directory."""
        mock_run_init.return_value = 0
        
        test_args = ["cdflow-init"]
        with patch.object(sys, 'argv', test_args):
            with patch('cdflow_cli.utils.config_paths.get_default_config_dir') as mock_get_default:
                mock_get_default.return_value = Path("/home/user/.config/cdflow")
                result = main()
                
                assert result == 0
                mock_run_init.assert_called_once()
                # Verify it was called with the string version of the path
                call_args = mock_run_init.call_args[1]
                assert "/home/user/.config/cdflow" in call_args['output_dir']
    
    @patch('cdflow_cli.cli.commands_init.run_init')
    def test_main_with_custom_config_dir(self, mock_run_init):
        """Test main function with custom config directory."""
        mock_run_init.return_value = 0
        
        test_args = ["cdflow-init", "--config-dir", "/custom/path"]
        with patch.object(sys, 'argv', test_args):
            result = main()
            
            assert result == 0
            mock_run_init.assert_called_once_with(
                output_dir="/custom/path",
                force=False,
                org_logo_path=None
            )
    
    @patch('cdflow_cli.cli.commands_init.run_init')
    def test_main_with_force_flag(self, mock_run_init):
        """Test main function with force flag."""
        mock_run_init.return_value = 0
        
        test_args = ["cdflow-init", "--force"]
        with patch.object(sys, 'argv', test_args):
            with patch('cdflow_cli.utils.config_paths.get_default_config_dir') as mock_get_default:
                mock_get_default.return_value = Path("/default")
                result = main()
                
                assert result == 0
                call_args = mock_run_init.call_args[1]
                assert call_args['force'] is True
    
    @patch('cdflow_cli.cli.commands_init.run_init')
    def test_main_with_org_logo(self, mock_run_init):
        """Test main function with organization logo."""
        mock_run_init.return_value = 0
        
        test_args = ["cdflow-init", "--org-logo", "/path/to/logo.png"]
        with patch.object(sys, 'argv', test_args):
            with patch('cdflow_cli.utils.config_paths.get_default_config_dir') as mock_get_default:
                mock_get_default.return_value = Path("/default")
                result = main()
                
                assert result == 0
                call_args = mock_run_init.call_args[1]
                assert call_args['org_logo_path'] == "/path/to/logo.png"
    
    @patch('cdflow_cli.cli.commands_init.run_init')
    def test_main_with_all_arguments(self, mock_run_init):
        """Test main function with all arguments provided."""
        mock_run_init.return_value = 1  # Test non-zero return code
        
        test_args = [
            "cdflow-init", 
            "--config-dir", "/custom/config",
            "--org-logo", "/custom/logo.svg",
            "--force"
        ]
        with patch.object(sys, 'argv', test_args):
            result = main()
            
            assert result == 1
            mock_run_init.assert_called_once_with(
                output_dir="/custom/config",
                force=True,
                org_logo_path="/custom/logo.svg"
            )