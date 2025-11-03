#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1
"""
Main cdflow CLI dispatcher with subcommands.

Usage:
    cdflow import --config config.yaml --log-level DEBUG
    cdflow rollback --config config.yaml
    cdflow --help
"""
import argparse
import importlib
import sys
from .commands_import import main as import_main
from .commands_rollback import main as rollback_main
from .commands_init import main as init_main

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    # Python < 3.8 fallback
    try:
        from importlib_metadata import version, PackageNotFoundError
    except ImportError:
        # Fallback if importlib_metadata not available
        version = None
        PackageNotFoundError = Exception


def get_version():
    """Get the installed package version."""
    if version is None:
        return "unknown (importlib.metadata not available)"

    try:
        return version("cdflow-cli")
    except PackageNotFoundError:
        return "unknown (development)"


def main():
    """Main entry point for cdflow CLI with subcommands."""
    parser = argparse.ArgumentParser(
        prog="cdflow",
        description="DonationFlow CLI - NationBuilder donation import and rollback tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cdflow --version               # Show version information
  cdflow init                    # Create config templates in default directory (~/.config/cdflow/)
  cdflow init --config-dir ~/.config/cdflow  # Create templates in specific directory
  cdflow import --config config.yaml
  cdflow import --type canadahelps --file donations/file.csv --config config.yaml
  cdflow import --type paypal --file /tmp/paypal.csv --config config.yaml
  cdflow rollback --config config.yaml --log-level DEBUG
        """,
    )

    parser.add_argument("--version", action="version", version=f"cdflow {get_version()}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands", metavar="COMMAND")

    # Init subcommand
    init_parser = subparsers.add_parser("init", help="Initialize configuration templates")
    init_parser.add_argument(
        "--config-dir", help="Directory to create configuration files (default: ~/.config/cdflow/)"
    )
    init_parser.add_argument(
        "--org-logo", help="Path to your organization's logo file to customize the interface"
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config files and logos without prompting",
    )

    # Import subcommand
    import_parser = subparsers.add_parser(
        "import", help="Import donations to NationBuilder from CSV files"
    )
    import_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Configuration file path (default: config.yaml)",
    )
    import_parser.add_argument(
        "--file",
        help="CSV file path to import (overrides config file)",
    )
    import_parser.add_argument(
        "--type",
        choices=["canadahelps", "paypal"],
        help="Import source type (overrides config file)",
    )
    import_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "NOTICE", "ERROR"],
        help="Console log level - NOTICE shows important milestones, ERROR shows only errors (default: INFO)",
    )

    # Rollback subcommand
    rollback_parser = subparsers.add_parser(
        "rollback", help="Rollback imported donations from NationBuilder"
    )
    rollback_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Configuration file path (default: config.yaml)",
    )
    rollback_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "NOTICE", "ERROR"],
        help="Console log level - NOTICE shows important milestones, ERROR shows only errors (default: INFO)",
    )

    args = parser.parse_args()

    # Validation: --type and --file must be used together or not at all
    if args.command == "import":
        if bool(getattr(args, "type", None)) != bool(getattr(args, "file", None)):
            parser.error("--type and --file must be used together or not at all")

    if args.command == "init":
        # Reconstruct sys.argv for the init command
        sys.argv = ["cdflow-init"]
        if args.config_dir:
            sys.argv.extend(["--config-dir", args.config_dir])
        if args.force:
            sys.argv.append("--force")
        if args.org_logo:
            sys.argv.extend(["--org-logo", args.org_logo])
        init_main()
    elif args.command == "import":
        # Reconstruct sys.argv for the import command
        sys_args = ["cdflow-import", "--config", args.config, "--log-level", args.log_level]
        if getattr(args, "type", None):
            sys_args.extend(["--type", args.type])
        if getattr(args, "file", None):
            sys_args.extend(["--file", args.file])
        sys.argv = sys_args
        import_main()
    elif args.command == "rollback":
        # Reconstruct sys.argv for the rollback command
        sys.argv = ["cdflow-rollback", "--config", args.config, "--log-level", args.log_level]
        rollback_main()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
