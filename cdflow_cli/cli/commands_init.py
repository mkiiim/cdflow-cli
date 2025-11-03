# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
cdflow init command for generating configuration templates.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
from cdflow_cli.utils import start_fresh_output

try:
    import pkg_resources

    _has_pkg_resources = True
except ImportError:
    _has_pkg_resources = False

try:
    from importlib import resources as importlib_resources

    _has_importlib_resources = True
except ImportError:
    _has_importlib_resources = False


def get_template_content(template_name: str) -> str:
    """
    Get config template content from package data.

    Args:
        template_name: Name of template file (e.g., 'local.yaml')

    Returns:
        Template content as string

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    try:
        if _has_importlib_resources:
            # Python 3.9+ preferred method
            import cdflow_cli.examples.config as templates_pkg

            content = importlib_resources.files(templates_pkg).joinpath(template_name).read_text()
            return content
        elif _has_pkg_resources:
            # Fallback for older Python versions
            content = pkg_resources.resource_string(
                "cdflow_cli", f"examples/config/{template_name}"
            ).decode("utf-8")
            return content
        else:
            # Last resort: try to find template relative to this file
            template_dir = Path(__file__).parent.parent / "examples" / "config"
            template_file = template_dir / template_name
            if template_file.exists():
                return template_file.read_text()
            else:
                raise FileNotFoundError(f"Template '{template_name}' not found")

    except Exception as e:
        raise FileNotFoundError(f"Template '{template_name}' not found in package: {e}")


def get_oauth_template_content(template_name: str) -> str:
    """
    Get OAuth template content from package data.

    Args:
        template_name: Name of template file (e.g., 'nb_local.env')

    Returns:
        Template content as string

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    try:
        if _has_importlib_resources:
            # Python 3.9+ preferred method
            import cdflow_cli.examples.oauth as oauth_templates_pkg

            content = importlib_resources.files(oauth_templates_pkg).joinpath(template_name).read_text()
            return content
        elif _has_pkg_resources:
            # Fallback for older Python versions
            content = pkg_resources.resource_string(
                "cdflow_cli", f"examples/oauth/{template_name}"
            ).decode("utf-8")
            return content
        else:
            # Last resort: try to find template relative to this file
            template_dir = Path(__file__).parent.parent / "examples" / "oauth"
            template_file = template_dir / template_name
            if template_file.exists():
                return template_file.read_text()
            else:
                raise FileNotFoundError(f"Template '{template_name}' not found")

    except Exception as e:
        raise FileNotFoundError(f"OAuth template '{template_name}' not found in package: {e}")


def get_plugin_files(adapter: str) -> List[str]:
    """
    Get list of plugin example files for an adapter from package data.

    Args:
        adapter: Adapter name (canadahelps, paypal)

    Returns:
        List of plugin filenames

    Raises:
        FileNotFoundError: If plugins directory doesn't exist
    """
    try:
        if _has_importlib_resources:
            # Python 3.9+ preferred method
            import cdflow_cli.examples.plugins as plugins_pkg

            adapter_path = importlib_resources.files(plugins_pkg) / adapter
            if not adapter_path.is_dir():
                return []

            # Get all .py files
            files = [f.name for f in adapter_path.iterdir() if f.name.endswith('.py')]
            return sorted(files)
        elif _has_pkg_resources:
            # Fallback for older Python versions
            resource_path = f"examples/plugins/{adapter}"
            if not pkg_resources.resource_exists("cdflow_cli", resource_path):
                return []

            files = pkg_resources.resource_listdir("cdflow_cli", resource_path)
            return sorted([f for f in files if f.endswith('.py')])
        else:
            # Last resort: try to find plugins relative to this file
            plugins_dir = Path(__file__).parent.parent / "examples" / "plugins" / adapter
            if not plugins_dir.exists():
                return []

            files = [f.name for f in plugins_dir.glob("*.py")]
            return sorted(files)

    except Exception as e:
        return []


def get_plugin_content(adapter: str, plugin_filename: str) -> str:
    """
    Get plugin file content from package data.

    Args:
        adapter: Adapter name (canadahelps, paypal)
        plugin_filename: Name of plugin file

    Returns:
        Plugin content as string

    Raises:
        FileNotFoundError: If plugin doesn't exist
    """
    try:
        if _has_importlib_resources:
            # Python 3.9+ preferred method
            import cdflow_cli.examples.plugins as plugins_pkg

            content = (importlib_resources.files(plugins_pkg) / adapter / plugin_filename).read_text()
            return content
        elif _has_pkg_resources:
            # Fallback for older Python versions
            content = pkg_resources.resource_string(
                "cdflow_cli", f"examples/plugins/{adapter}/{plugin_filename}"
            ).decode("utf-8")
            return content
        else:
            # Last resort: try to find plugin relative to this file
            plugin_file = Path(__file__).parent.parent / "examples" / "plugins" / adapter / plugin_filename
            if plugin_file.exists():
                return plugin_file.read_text()
            else:
                raise FileNotFoundError(f"Plugin '{plugin_filename}' not found")

    except Exception as e:
        raise FileNotFoundError(f"Plugin '{adapter}/{plugin_filename}' not found in package: {e}")


def check_file_conflicts(output_dir: Path, template_files: List[str]) -> List[Path]:
    """
    Check for existing files that would conflict with templates.

    Args:
        output_dir: Directory where templates would be created
        template_files: List of template filenames to check

    Returns:
        List of existing file paths that would conflict
    """
    conflicts = []
    for template_file in template_files:
        target_file = output_dir / template_file
        if target_file.exists():
            conflicts.append(target_file)
    return conflicts


def prompt_overwrite_decision(conflicts: List[Path]) -> bool:
    """
    Prompt user for overwrite decision when conflicts exist.

    Args:
        conflicts: List of conflicting file paths

    Returns:
        True if user wants to overwrite, False otherwise
    """
    print(f"\n⚠️  The following files already exist:")
    for conflict in conflicts:
        print(f"   - {conflict}")

    print(f"\nChoose an action:")
    print(f"  [o] Overwrite existing files")
    print(f"  [s] Skip existing files (create only missing ones)")
    print(f"  [c] Cancel operation")

    while True:
        choice = input(f"\nEnter your choice [o/s/c]: ").lower().strip()

        if choice in ["o", "overwrite"]:
            return True
        elif choice in ["s", "skip"]:
            return False
        elif choice in ["c", "cancel"]:
            print("Operation cancelled.")
            return None
        else:
            print("Invalid choice. Please enter 'o', 's', or 'c'.")


def copy_template_file(
    template_name: str, output_path: Path, force_overwrite: bool = False
) -> bool:
    """
    Copy a single template file from package to target location.

    Args:
        template_name: Name of template in package
        output_path: Where to write the file
        force_overwrite: Whether to overwrite existing files

    Returns:
        True if file was created, False if skipped
    """
    if output_path.exists() and not force_overwrite:
        print(f"   Skipping {output_path} (already exists)")
        return False

    try:
        template_content = get_template_content(template_name)
        output_path.write_text(template_content)

        status = "Created" if not output_path.exists() else "Overwritten"
        print(f"   ✅ {status} {output_path}")
        return True

    except Exception as e:
        print(f"   ❌ Failed to create {output_path}: {e}")
        return False


def copy_oauth_template_file(
    template_name: str, output_path: Path, force_overwrite: bool = False
) -> bool:
    """
    Copy a single OAuth template file from package to target location.

    Args:
        template_name: Name of template in package
        output_path: Where to write the file
        force_overwrite: Whether to overwrite existing files

    Returns:
        True if file was created, False if skipped
    """
    if output_path.exists() and not force_overwrite:
        print(f"   Skipping {output_path} (already exists)")
        return False

    try:
        template_content = get_oauth_template_content(template_name)
        output_path.write_text(template_content)

        status = "Created" if not output_path.exists() else "Overwritten"
        print(f"   ✅ {status} {output_path}")
        return True

    except Exception as e:
        print(f"   ❌ Failed to create {output_path}: {e}")
        return False


def copy_plugin_file(
    adapter: str, plugin_filename: str, output_path: Path, force_overwrite: bool = False
) -> bool:
    """
    Copy a single plugin file from package to target location.

    Args:
        adapter: Adapter name (canadahelps, paypal)
        plugin_filename: Name of plugin file
        output_path: Where to write the file
        force_overwrite: Whether to overwrite existing files

    Returns:
        True if file was created, False if skipped
    """
    if output_path.exists() and not force_overwrite:
        print(f"   Skipping {output_path} (already exists)")
        return False

    try:
        plugin_content = get_plugin_content(adapter, plugin_filename)
        output_path.write_text(plugin_content)

        status = "Created" if not output_path.exists() else "Overwritten"
        print(f"   ✅ {status} {output_path}")
        return True

    except Exception as e:
        print(f"   ❌ Failed to create {output_path}: {e}")
        return False


def setup_org_logo(config_dir: Path, org_logo_path: str, force: bool = False) -> bool:
    """
    Set up organization logo for PyPI users.

    Args:
        config_dir: Configuration directory path
        org_logo_path: Path to source organization logo
        force: Force overwrite existing logo

    Returns:
        bool: True if setup successful
    """
    import shutil

    try:
        source_logo = Path(org_logo_path)
        if not source_logo.exists():
            print(f"   ❌ Logo file not found: {org_logo_path}")
            return False

        if not source_logo.is_file():
            print(f"   ❌ Logo path is not a file: {org_logo_path}")
            return False

        # Create assets directory structure
        assets_dir = config_dir / "assets" / "logos" / "custom"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Copy logo file
        target_logo = assets_dir / "org-logo-square.png"
        if target_logo.exists() and not force:
            print(f"   ⏭️  Logo already exists: {target_logo}")
            print(f"      Use --force to overwrite")
            return False

        shutil.copy2(source_logo, target_logo)
        print(f"   📝 Copied logo: {source_logo} → {target_logo}")

        # Update config template to enable custom logos
        config_file = config_dir / "local.yaml"
        if config_file.exists():
            try:
                # Read current config
                config_content = config_file.read_text()

                # Enable custom logos if not already enabled
                if "use_custom: false" in config_content:
                    config_content = config_content.replace("use_custom: false", "use_custom: true")
                    config_file.write_text(config_content)
                    print(f"   ✅ Enabled custom logos in {config_file}")
                elif "use_custom: true" not in config_content:
                    print(f"   ℹ️  Custom logos setting not found in config template")

            except Exception as e:
                print(f"   ⚠️  Could not update config template: {e}")

        return True

    except Exception as e:
        print(f"   ❌ Logo setup failed: {e}")
        return False


def run_init(
    output_dir: str = ".", force: bool = False, org_logo_path: Optional[str] = None
) -> int:
    """
    Initialize cdflow configuration templates.

    Args:
        output_dir: Directory to create templates in
        force: Force overwrite existing files without prompting
        org_logo_path: Optional path to organization logo file

    Returns:
        Exit code (0 = success, 1 = error)
    """
    output_path = Path(output_dir).resolve()

    # Validate output directory
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created directory: {output_path}")
        except Exception as e:
            print(f"❌ Error: Cannot create directory {output_path}: {e}")
            return 1

    if not output_path.is_dir():
        print(f"❌ Error: {output_path} is not a directory")
        return 1

    # Check write permissions
    if not output_path.expanduser().exists():
        print(f"❌ Error: Cannot write to directory {output_path}")
        return 1

    # Define config templates to create in config directory
    config_templates = [
        ("local.yaml", "local.yaml"),
    ]
    
    # Define OAuth templates to create in ~/.env/ directory  
    oauth_templates = [
        ("nb_local.env", "nb_local.env"),
    ]

    start_fresh_output()
    print(f"🚀 Initializing cdflow configuration in: {output_path}")

    # Check for file conflicts (config files only)
    config_target_files = [output_filename for _, output_filename in config_templates]
    conflicts = check_file_conflicts(output_path, config_target_files)
    
    # Check for OAuth file conflicts in ~/.env directory
    env_path = Path.home() / ".env"
    oauth_target_files = [output_filename for _, output_filename in oauth_templates]
    oauth_conflicts = check_file_conflicts(env_path, oauth_target_files)

    overwrite_all = force
    skip_existing = False

    if (conflicts or oauth_conflicts) and not force:
        all_conflicts = conflicts + oauth_conflicts
        decision = prompt_overwrite_decision(all_conflicts)
        if decision is None:  # User cancelled
            return 1
        elif decision:  # Overwrite
            overwrite_all = True
        else:  # Skip
            skip_existing = True

    # Create template files
    created_count = 0
    skipped_count = 0

    print(f"\n📝 Creating configuration templates:")

    for template_name, output_filename in config_templates:
        output_file = output_path / output_filename

        # Determine if we should create this file
        should_create = True
        force_this_file = overwrite_all

        if output_file.exists() and skip_existing:
            should_create = False

        if should_create:
            if copy_template_file(template_name, output_file, force_this_file):
                created_count += 1
            else:
                skipped_count += 1
        else:
            print(f"   Skipping {output_file} (already exists)")
            skipped_count += 1

    # Create OAuth template files in ~/.env directory
    print(f"\n🔐 Creating OAuth templates in ~/.env directory:")

    # Ensure ~/.env directory exists
    env_path.mkdir(exist_ok=True)

    for template_name, output_filename in oauth_templates:
        output_file = env_path / output_filename

        # Determine if we should create this file
        should_create = True
        force_this_file = overwrite_all

        if output_file.exists() and skip_existing:
            should_create = False

        if should_create:
            if copy_oauth_template_file(template_name, output_file, force_this_file):
                created_count += 1
            else:
                skipped_count += 1
        else:
            print(f"   Skipping {output_file} (already exists)")
            skipped_count += 1

    # Copy plugin examples
    print(f"\n🔌 Copying plugin examples:")
    plugins_base_path = output_path / "plugins"

    adapters = ["canadahelps", "paypal"]
    for adapter in adapters:
        adapter_plugins_path = plugins_base_path / adapter
        adapter_plugins_path.mkdir(parents=True, exist_ok=True)

        plugin_files = get_plugin_files(adapter)
        if plugin_files:
            print(f"   {adapter}:")
            for plugin_filename in plugin_files:
                output_file = adapter_plugins_path / plugin_filename

                # Determine if we should create this file
                should_create = True
                force_this_file = overwrite_all

                if output_file.exists() and skip_existing:
                    should_create = False

                if should_create:
                    if copy_plugin_file(adapter, plugin_filename, output_file, force_this_file):
                        created_count += 1
                    else:
                        skipped_count += 1
                else:
                    print(f"      Skipping {plugin_filename} (already exists)")
                    skipped_count += 1

    # Handle organization logo setup if provided
    logo_setup_success = False
    if org_logo_path:
        logo_setup_success = setup_org_logo(output_path, org_logo_path, force)

    # Summary
    print(f"\n✨ Initialization complete:")
    if created_count > 0:
        print(f"   📝 Created {created_count} new template file(s)")
    if skipped_count > 0:
        print(f"   ⏭️  Skipped {skipped_count} existing file(s)")
    if logo_setup_success:
        print(f"   🎨 Set up custom organization logo")

    # Construct path to load-secrets.sh script and reference actual created files
    script_dir = Path(__file__).parent.parent
    load_secrets_script = script_dir / "scripts" / "load-secrets.sh"
    config_file = output_path / "local.yaml"
    env_file = Path.home() / ".env" / "nb_local.env"
    plugins_dir = output_path / "plugins"

    print(f"\n🔧 Next steps:")
    print(f"   1. Edit {config_file} with your storage paths")
    print(f"   2. Edit {env_file} with your NationBuilder OAuth credentials")
    print(f"   3. Load secrets: source {load_secrets_script} {env_file}")
    print(f"   4. Review plugin examples in {plugins_dir}")
    print(f"      Plugins start with _ (disabled). Remove _ to enable.")
    if logo_setup_success:
        print(f"   5. Your organization logo is ready (use_custom: true is set)")
        print(f"   6. Run: cdflow import --config {config_file}")
    else:
        print(f"   5. Run: cdflow import --config {config_file}")

    print(f"\n")
    return 0



def main():
    """Main entry point for cdflow init command."""
    from ..utils.config_paths import get_default_config_dir

    parser = argparse.ArgumentParser(
        prog="cdflow init", description="Initialize cdflow configuration templates"
    )

    parser.add_argument(
        "--config-dir", help="Directory to create configuration files (default: ~/.config/cdflow/)"
    )

    parser.add_argument(
        "--org-logo", help="Path to your organization's logo file to customize the interface"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config files and logos without prompting",
    )

    args = parser.parse_args()

    # Use smart default config directory if not specified
    config_dir = args.config_dir
    if not config_dir:
        config_dir = str(get_default_config_dir())

    return run_init(output_dir=config_dir, force=args.force, org_logo_path=args.org_logo)


if __name__ == "__main__":
    sys.exit(main())
