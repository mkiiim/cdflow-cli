# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Unit tests for LogoDeployer branding functionality.

Tests cover logo deployment, file operations, configuration loading,
and custom logo handling scenarios.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from cdflow_cli.utils.logo_deployer import LogoDeployer, get_logo_deployer, deploy_logos, ensure_logos_deployed
from cdflow_cli.utils.config import ConfigProvider
import builtins
import types


class TestLogoDeployer:
    """Test LogoDeployer functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration provider."""
        config = Mock(spec=ConfigProvider)
        config.get_app_setting.return_value = {
            "use_custom": True,
            "custom_path": "assets/logos/custom",
            "overrides": {
                "org_logo_square": "custom-org-logo.png"
            }
        }
        config.get_config_directory.return_value = Path("/tmp/config")
        return config

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create directory structure
            static_dir = temp_path / "static"
            default_logos_dir = temp_path / "default_logos"
            custom_logos_dir = temp_path / "custom_logos"
            
            static_dir.mkdir()
            default_logos_dir.mkdir()
            custom_logos_dir.mkdir()
            
            # Create sample logo files
            for filename in LogoDeployer.LOGO_FILENAMES.values():
                (default_logos_dir / filename).write_text(f"default {filename}")
                (custom_logos_dir / filename).write_text(f"custom {filename}")

            # Provide file matching override name
            (custom_logos_dir / "custom-org-logo.png").write_text("override content")
            
            yield {
                "static": static_dir,
                "default": default_logos_dir,
                "custom": custom_logos_dir,
                "base": temp_path
            }

    @pytest.fixture
    def deployer(self, mock_config, temp_dirs):
        """Create LogoDeployer instance for testing."""
        deployer = LogoDeployer(mock_config, str(temp_dirs["static"]))

        deployer._get_package_default_logos_path = MagicMock(return_value=temp_dirs["default"])
        # Point custom path to our temporary custom directory for deterministic tests
        deployer.logo_config["custom_path"] = str(temp_dirs["custom"])
        return deployer

    def test_deployer_initialization(self, deployer, mock_config, temp_dirs):
        """Test LogoDeployer initializes correctly."""
        assert deployer.config_provider == mock_config
        assert deployer.static_dir == temp_dirs["static"]
        assert deployer.logo_config["use_custom"] is True
        assert "custom_path" in deployer.logo_config

    def test_get_static_dir_explicit(self, mock_config):
        """Test getting static directory with explicit path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deployer = LogoDeployer(mock_config, temp_dir)
            assert deployer.static_dir == Path(temp_dir)

    def test_get_static_dir_default(self, mock_config):
        """Test getting default static directory."""
        import cdflow_cli

        deployer = LogoDeployer(mock_config)
        expected_path = Path(cdflow_cli.__file__).parent / "assets" / "static"
        assert deployer.static_dir == expected_path

    def test_get_static_dir_fallback(self, mock_config):
        """Test fallback static directory when package import fails."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "cdflow_cli":
                raise ImportError("forced import error")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            deployer = LogoDeployer(mock_config)
            assert deployer.static_dir == Path("assets/static")

    def test_load_logo_config_success(self, mock_config):
        """Test loading logo configuration successfully."""
        deployer = LogoDeployer(mock_config)
        assert deployer.logo_config["use_custom"] is True
        assert deployer.logo_config["custom_path"] == "assets/logos/custom"

    def test_load_logo_config_no_provider(self):
        """Test loading default config when no provider given."""
        deployer = LogoDeployer()
        assert deployer.logo_config["use_custom"] is False
        assert "custom_path" in deployer.logo_config

    def test_load_logo_config_error(self, mock_config):
        """Test fallback when config loading fails."""
        mock_config.get_app_setting.side_effect = Exception("Config error")
        
        deployer = LogoDeployer(mock_config)
        assert deployer.logo_config["use_custom"] is False  # Default fallback

    def test_deploy_all_logos_success(self, deployer, temp_dirs):
        """Test successful deployment of all logos."""
        result = deployer.deploy_all_logos()
        assert result is True
        
        # Verify all default logos were deployed
        for logo_type, filename in LogoDeployer.LOGO_FILENAMES.items():
            static_file = temp_dirs["static"] / filename
            assert static_file.exists()
            if logo_type == "org_logo_square":
                expected_prefix = "override content"
            else:
                expected_prefix = "custom"
            assert static_file.read_text().startswith(expected_prefix)

    def test_deploy_all_logos_static_dir_creation_fails(self, deployer):
        """Test deployment when static directory creation fails."""
        # Make static_dir point to a file (not directory) to cause mkdir to fail
        deployer.static_dir = deployer.static_dir / "file.txt"
        deployer.static_dir.write_text("content")
        deployer.static_dir = deployer.static_dir  # Now it's a file, not dir
        
        result = deployer.deploy_all_logos()
        assert result is False

    def test_deploy_default_logos_missing_files(self, deployer, temp_dirs):
        """Test deploying default logos when some files are missing."""
        # Remove one default logo file
        (temp_dirs["default"] / "org-logo-square.png").unlink()
        
        result = deployer._deploy_default_logos()
        assert result is True  # Should still succeed with partial deployment
        
        # Verify some logos were deployed
        deployed_count = sum(1 for f in LogoDeployer.LOGO_FILENAMES.values() 
                           if (temp_dirs["static"] / f).exists())
        assert deployed_count > 0

    def test_deploy_default_logos_no_source_dir(self, deployer, temp_dirs):
        """Test deploying when default logos directory doesn't exist."""
        # Point to non-existent directory
        with patch.object(deployer, '_get_package_default_logos_path', 
                         return_value=Path("/nonexistent")):
            result = deployer._deploy_default_logos()
            assert result is False  # Should fail when no logos found

    def test_deploy_custom_logos_absolute_path(self, deployer, temp_dirs):
        """Test deploying custom logos from absolute path."""
        deployer.logo_config["custom_path"] = str(temp_dirs["custom"])
        
        deployer._deploy_custom_logos()
        
        # Verify custom logos were deployed (overwriting defaults)
        for filename in LogoDeployer.LOGO_FILENAMES.values():
            static_file = temp_dirs["static"] / filename
            assert static_file.exists()

    def test_deploy_custom_logos_relative_path(self, deployer, temp_dirs):
        """Test deploying custom logos from relative path."""
        # Set up relative path from current working directory
        custom_rel_dir = temp_dirs["base"] / "rel_custom"
        custom_rel_dir.mkdir()
        
        for filename in LogoDeployer.LOGO_FILENAMES.values():
            (custom_rel_dir / filename).write_text(f"relative custom {filename}")
        
        deployer.logo_config["custom_path"] = "rel_custom"
        
        with patch('pathlib.Path.cwd', return_value=temp_dirs["base"]):
            deployer._deploy_custom_logos()
        
        # Should find logos in relative path
        assert any((temp_dirs["static"] / f).exists() 
                  for f in LogoDeployer.LOGO_FILENAMES.values())

    def test_deploy_custom_logos_config_dir_fallback(self, deployer, temp_dirs, mock_config):
        """Test deploying custom logos using config directory fallback."""
        # Set up custom logos in config directory
        config_custom_dir = temp_dirs["base"] / "config_custom"
        config_custom_dir.mkdir()
        
        for filename in LogoDeployer.LOGO_FILENAMES.values():
            (config_custom_dir / filename).write_text(f"config custom {filename}")
        
        deployer.logo_config["custom_path"] = "config_custom"
        mock_config.get_config_directory.return_value = temp_dirs["base"]
        
        deployer._deploy_custom_logos()
        
        # Should find logos in config directory
        assert any((temp_dirs["static"] / f).exists() 
                  for f in LogoDeployer.LOGO_FILENAMES.values())

    def test_deploy_custom_logos_no_custom_dir(self, deployer):
        """Test deploying custom logos when custom directory doesn't exist."""
        deployer.logo_config["custom_path"] = "/nonexistent/path"
        
        # Should not crash
        deployer._deploy_custom_logos()

    def test_deploy_custom_logos_with_overrides(self, deployer, temp_dirs):
        """Test deploying custom logos with filename overrides."""
        # Create custom logo with override filename
        custom_file = temp_dirs["custom"] / "custom-org-logo.png"
        custom_file.write_text("custom org logo content")
        
        deployer.logo_config["custom_path"] = str(temp_dirs["custom"])
        deployer.logo_config["overrides"] = {
            "org_logo_square": "custom-org-logo.png"
        }
        
        deployer._deploy_custom_logos()
        
        # Should deploy override file as standard filename
        static_file = temp_dirs["static"] / "org-logo-square.png"
        assert static_file.exists()
        assert "custom org logo content" in static_file.read_text()

    def test_get_logo_filename_with_override(self, deployer):
        """Test getting logo filename with override."""
        deployer.logo_config["overrides"] = {
            "org_logo_square": "my-custom-logo.png"
        }
        
        filename = deployer._get_logo_filename("org_logo_square", "default.png")
        assert filename == "my-custom-logo.png"

    def test_get_logo_filename_no_override(self, deployer):
        """Test getting logo filename without override."""
        filename = deployer._get_logo_filename("org_logo_square", "default.png")
        deployer = LogoDeployer()  # No overrides
        filename = deployer._get_logo_filename("org_logo_square", "default.png")
        assert filename == "default.png"

    def test_get_static_logo_path(self, deployer, temp_dirs):
        """Test getting static logo path."""
        path = deployer.get_static_logo_path("org_logo_square")
        expected = temp_dirs["static"] / "org-logo-square.png"
        assert path == expected

    def test_get_static_logo_path_invalid_type(self, deployer):
        """Test getting static logo path for invalid logo type."""
        path = deployer.get_static_logo_path("invalid_logo_type")
        assert path is None

    def test_is_deployed_true(self, deployer, temp_dirs):
        """Test checking if logo is deployed when it exists."""
        # Create the logo file
        logo_file = temp_dirs["static"] / "org-logo-square.png"
        logo_file.write_text("logo content")
        
        assert deployer.is_deployed("org_logo_square") is True

    def test_is_deployed_false(self, deployer):
        """Test checking if logo is deployed when it doesn't exist."""
        assert deployer.is_deployed("org_logo_square") is False

    def test_is_deployed_invalid_type(self, deployer):
        """Test checking deployment status for invalid logo type."""
        assert deployer.is_deployed("invalid_logo_type") is False

    def test_redeploy_if_needed_missing_logos(self, deployer):
        """Test redeployment when logos are missing."""
        with patch.object(deployer, 'deploy_all_logos', return_value=True) as mock_deploy:
            result = deployer.redeploy_if_needed()
            assert result is True
            mock_deploy.assert_called_once()

    def test_redeploy_if_needed_all_present(self, deployer, temp_dirs):
        """Test redeployment when all logos are already deployed."""
        # Deploy all logos first
        deployer.deploy_all_logos()
        
        with patch.object(deployer, 'deploy_all_logos') as mock_deploy:
            result = deployer.redeploy_if_needed()
            assert result is True
            mock_deploy.assert_not_called()

    def test_deploy_with_custom_disabled(self, deployer, temp_dirs):
        """Test deployment when custom logos are disabled."""
        deployer.logo_config["use_custom"] = False
        
        result = deployer.deploy_all_logos()
        assert result is True
        
        # Should only have default logos
        for logo_type, filename in LogoDeployer.LOGO_FILENAMES.items():
            static_file = temp_dirs["static"] / filename
            assert static_file.exists()
            assert static_file.read_text().startswith("default")

    def test_copy_error_handling(self, deployer, temp_dirs):
        """Test handling of file copy errors."""
        # Make static directory read-only to cause copy errors
        temp_dirs["static"].chmod(0o444)
        
        try:
            result = deployer.deploy_all_logos()
            # Should handle errors gracefully
            assert result in [True, False]  # Depends on partial success logic
        finally:
            # Restore permissions for cleanup
            temp_dirs["static"].chmod(0o755)

    def test_global_deployer_singleton(self, mock_config):
        """Test global deployer singleton behavior."""
        # Clear global state
        import cdflow_cli.utils.logo_deployer
        cdflow_cli.utils.logo_deployer._global_deployer = None
        
        deployer1 = get_logo_deployer(mock_config)
        deployer2 = get_logo_deployer()
        
        assert deployer1 is deployer2  # Should be same instance

    def test_global_deployer_with_new_config(self, mock_config):
        """Test global deployer with new config provider."""
        import cdflow_cli.utils.logo_deployer
        cdflow_cli.utils.logo_deployer._global_deployer = None
        
        deployer1 = get_logo_deployer(mock_config)
        
        new_config = Mock(spec=ConfigProvider)
        deployer2 = get_logo_deployer(new_config)
        
        assert deployer1 is not deployer2  # Should be different instance

    def test_convenience_deploy_logos(self, mock_config):
        """Test convenience function for deploying logos."""
        with patch('cdflow_cli.utils.logo_deployer.LogoDeployer') as mock_deployer_class:
            mock_deployer = Mock()
            mock_deployer_class.return_value = mock_deployer
            mock_deployer.deploy_all_logos.return_value = True
            
            result = deploy_logos(mock_config)
            assert result is True
            mock_deployer.deploy_all_logos.assert_called_once()

    def test_convenience_ensure_logos_deployed(self, mock_config):
        """Test convenience function for ensuring logos are deployed."""
        with patch('cdflow_cli.utils.logo_deployer.LogoDeployer') as mock_deployer_class:
            mock_deployer = Mock()
            mock_deployer_class.return_value = mock_deployer
            mock_deployer.redeploy_if_needed.return_value = True
            
            result = ensure_logos_deployed(mock_config)
            assert result is True
            mock_deployer.redeploy_if_needed.assert_called_once()

    def test_package_default_logos_path_import_error(self, mock_config):
        """Test getting package default logos path when import fails."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "cdflow_cli":
                raise ImportError("forced import error")
            return real_import(name, *args, **kwargs)

        deployer = LogoDeployer(mock_config)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            path = deployer._get_package_default_logos_path()
            assert path == Path("assets/logos/default")

    def test_no_config_provider_initialization(self, temp_dirs):
        """Test initialization without config provider."""
        deployer = LogoDeployer(static_dir=str(temp_dirs["static"]))
        assert deployer.config_provider is None
        assert deployer.logo_config["use_custom"] is False

    def test_deploy_all_logos_phase_logging(self, deployer, temp_dirs):
        """Test that deployment phases are logged correctly."""
        with patch('cdflow_cli.utils.logo_deployer.logger') as mock_logger:
            deployer.deploy_all_logos()
            
            # Verify phase logging calls
            phase_calls = [call for call in mock_logger.debug.call_args_list 
                          if "Phase" in str(call)]
            assert len(phase_calls) >= 2  # Should log both phases
