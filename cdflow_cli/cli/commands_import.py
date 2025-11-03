# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Command-line interface commands for donation import functionality.
"""

import os
import sys
import yaml
import logging
import chardet
import argparse
import datetime
import uuid
import time
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from cdflow_cli.utils import start_fresh_output, clear_screen

from ..utils.config import ConfigProvider
from ..utils.logging import get_logging_provider, LoggingProvider, FileLoggingProvider

# Initialize module-level logger
logger = logging.getLogger(__name__)




def get_encoding(file_path: str, paths=None) -> Tuple[str, float]:
    """
    Determine a file's encoding using paths system.

    Args:
        file_path: Path to the file (relative for CLI, full path otherwise)
        paths: Paths system for file access

    Returns:
        Tuple of (encoding, confidence)
    """
    try:
        # Use paths system for file access
        # Determine if this is CLI or API usage based on the input filename
        if "/" in file_path and (
            file_path.startswith("canadahelps/") or file_path.startswith("paypal/")
        ):
            # API usage - read from app_processing directory
            full_file_path = paths.app_processing / file_path
        else:
            # CLI usage - read from cli_source directory
            full_file_path = paths.cli_source / file_path

        with open(full_file_path, "rb") as f:
            sample = f.read(10000)

        result = chardet.detect(sample)
        return result["encoding"], result["confidence"]
    except Exception as e:
        logger.error(f"Error detecting file encoding: {str(e)}")
        return "utf-8", 0.0  # Default to UTF-8 with low confidence


def initialize_logging(
    config_provider: ConfigProvider, early_init: bool = False
) -> Tuple[LoggingProvider, Optional[str]]:
    """
    Initialize logging using the configuration provider.

    Args:
        config_provider: Configuration provider containing logging settings
        early_init: Whether this is an early initialization

    Returns:
        Tuple of (LoggingProvider, log_path or None)
    """
    # Get logging configuration
    logging_config = config_provider.get_logging_config()

    # If no logging configuration exists, use default
    if not logging_config:
        logging_config = {
            "provider": "file",
            "settings": {"directory": "./logs", "level": "DEBUG", "console_level": "INFO"},
        }

    # Create the logging provider
    logging_provider = get_logging_provider(logging_config)

    # Set log level from runtime settings if specified
    # Get log level from new logging config structure
    file_level = logging_config.get("file_level", "DEBUG") if logging_config else "DEBUG"
    log_level = file_level if file_level != "NONE" else "DEBUG"

    # Configure logging
    if early_init:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        log_filename = f"IMPORTDONATIONS_{timestamp}_early_init.log"
        log_path = logging_provider.configure_logging(
            log_filename=log_filename, log_level=log_level or "DEBUG", early_init=True
        )
        return logging_provider, log_path
    else:
        logging_provider.configure_logging(log_level=log_level or "DEBUG", early_init=False)
        return logging_provider, None


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments including config, log_level, type, and file

    Raises:
        SystemExit: If config file not specified
    """
    parser = argparse.ArgumentParser(description="DonationFlow Import Tool")
    parser.add_argument(
        "--config", required=True, help="Path to configuration YAML file (required)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "NOTICE", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    parser.add_argument(
        "--type",
        choices=["canadahelps", "paypal"],
        help="Import source type (overrides config file)",
    )
    parser.add_argument("--file", help="CSV file path to import (overrides config file)")
    args = parser.parse_args()
    return args


def prompt_for_confirmation(nation_slug: str, input_filename: str, source_type: str) -> bool:
    """
    Prompt user to confirm import operation.

    Args:
        nation_slug (str): NationBuilder nation slug
        input_filename (str): Input file path
        source_type (str): Source type ('CanadaHelps' or 'PayPal')

    Returns:
        bool: True if confirmed, False otherwise
    """
    # clear_screen()
    start_fresh_output()
    print("\n")
    logger.info(f"🚀 Starting {source_type} Import")
    logger.info(f"📁 Processing file: {input_filename}")
    logger.info(f"🎯 NationBuilder environment: {nation_slug}")
    logger.info(f"{'─'*40}")
    print("\n")

    try:
        input("Press Enter to continue, CTRL-C to abort...\n")
        return True
    except KeyboardInterrupt:
        logger.info("🚫 Import cancelled by user.")
        return False


def run_cli(config=None, logging_provider=None) -> int:
    """
    Run the command-line interface for donation import.

    Args:
        config: ConfigProvider instance (from bootstrap)
        storage: Storage provider instance (from bootstrap)
        logging_provider: Logging provider instance (from bootstrap)

    Returns:
        int: Exit status code (0 for success, non-zero for errors)
    """
    # Use providers from bootstrap (same pattern as API server)
    if not all([config, logging_provider]):
        # Fallback for backward compatibility if called without parameters
        early_logging_provider = FileLoggingProvider(base_path="./logs", console_level="INFO")
        early_logging_provider.initialize_bootstrap_logging()
        logger = early_logging_provider.get_logger(__name__)
        logger.debug("Fallback: Bootstrap logging initialized")
        logging_provider = early_logging_provider
    else:
        logger = logging_provider.get_logger(__name__)
        logger.debug("Using providers from bootstrap initialization")

    try:
        # Display startup message with formatting
        # clear_screen()
        start_fresh_output()
        print("\n")
        logger.info("🚀 Launching DonationFlow Import Donations...")
        logger.info(f"{'─'*40}")
        print("\n")

        # If no providers given, we need to handle fallback initialization
        if not all([config, logging_provider]):
            # Get config file path from command-line arguments or prompt
            args = parse_arguments()
            config_path = args.config
            if not config_path:
                config_path = input("Please enter the DonationFlow config YAML filename: ")

            # Apply smart config path resolution
            from ..utils.config_paths import resolve_config_path

            resolved_config_path = resolve_config_path(config_path)

            # Check if the configuration file exists
            if not resolved_config_path.exists():
                print("DonationFlow config file does not exist / not found")
                logger.error(f"Config file not found: {resolved_config_path}")
                return 1

            # Initialize configuration provider
            logger.debug(f"Loading config from {resolved_config_path}")
            config = ConfigProvider(str(resolved_config_path))
            logger.debug(f"Configuration loaded from {config_path}")

            # Update logging provider
            logging_config = config.get_logging_config()
            if logging_config:
                logging_provider = get_logging_provider(logging_config)
                logger = logging_provider.get_logger(__name__)

        # Initialize paths system for direct Path operations
        from ..utils.paths import initialize_paths

        paths = initialize_paths(config)
        logger.debug(f"Paths system initialized: {paths}")

        # Initialize NationBuilderOAuth and get tokens for CLI job system
        from ..adapters.nationbuilder import NationBuilderOAuth

        # Ensure redirect_uri and callback_port are present for CLI context
        # These values are not functionally used by the CLI, but are required by NationBuilderOAuth constructor
        deployment_hostname = config.get_app_setting(["deployment", "hostname"], "localhost")
        deployment_api_port = config.get_app_setting(
            ["deployment", "api_port"], 8000
        )  # Use API port

        cli_redirect_uri = f"http://{deployment_hostname}:{deployment_api_port}/callback"

        oauth_config_to_use = config.get_oauth_config()
        if not oauth_config_to_use:
            logger.error("OAuth configuration not found in environment variables")
            return 1

        if "redirect_uri" not in oauth_config_to_use:
            oauth_config_to_use["redirect_uri"] = cli_redirect_uri
        if "callback_port" not in oauth_config_to_use:
            oauth_config_to_use["callback_port"] = deployment_api_port

        # Ensure logos are deployed before OAuth (uses custom config if specified)
        try:
            from ..utils.logo_deployer import ensure_logos_deployed

            logger.debug("Ensuring logos are deployed before OAuth initialization")
            ensure_logos_deployed(config)  # Pass the config provider with custom logo settings
            logger.debug("Logo deployment completed successfully")
        except Exception as e:
            logger.warning(
                f"Logo deployment failed, OAuth will continue but logos may not display correctly: {e}"
            )

        nboauth = NationBuilderOAuth(oauth_config_to_use, auto_initialize=False)

        logger.debug("Explicitly initializing OAuth token for CLI job system")
        if not nboauth.initialize():
            logger.error("Failed to initialize OAuth token for CLI job system")
            return 1

        oauth_tokens = {
            "access_token": nboauth.nb_jwt_token,
            "refresh_token": nboauth.nb_refresh_token,
            "expires_in": nboauth.nb_token_expires_in,
            "created_at": nboauth.nb_token_created_at,
        }
        logger.debug(
            f"OAuth tokens obtained for CLI job system (access token ends with ...{oauth_tokens['access_token'][-5:]})"
        )

        # Always use job system - legacy direct processing removed
        logger.debug("CLI using job system for processing")

        # Initialize job manager for CLI job system integration
        from ..jobs import JobManager

        job_manager = JobManager(config, logging_provider)

        # Run CLI with job system
        return run_cli_with_jobs(job_manager, config, oauth_tokens)
    except Exception as e:
        # Ensure we log any unexpected exceptions
        if logging_provider:
            logger = logging_provider.get_logger(__name__)
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        else:
            print(f"Unhandled exception: {str(e)}")
        return 1
    finally:
        # Clean up logging if needed
        if logging_provider:
            logging_provider.shutdown()


def validate_import_file(
    file_path: str, config: ConfigProvider, resolve_from_cwd: bool = False
) -> Path:
    """
    Enhanced file validation with user-friendly errors.

    Args:
        file_path: Path to the file (relative to cli_source or cwd, or absolute)
        config: Configuration provider for paths
        resolve_from_cwd: If True, resolve relative paths from current working directory
                         If False, resolve relative paths from cli_source storage path

    Returns:
        Path: Validated absolute path to the file

    Raises:
        FileNotFoundError: If file doesn't exist with clear error message
        ValueError: If path exists but is not a file
    """
    from ..utils.paths import initialize_paths

    source_path = Path(file_path)

    if not source_path.is_absolute():
        if resolve_from_cwd:
            # CLI flag context: resolve relative to current working directory
            source_path = Path.cwd() / source_path
            resolution_context = f"Current working directory: {Path.cwd()}"
        else:
            # Config file context: resolve relative to cli_source storage path
            paths = initialize_paths(config)
            cli_source_path = paths.get_path("cli_source")
            source_path = cli_source_path / source_path
            resolution_context = f"CLI source directory: {cli_source_path}"
    else:
        resolution_context = "Absolute path provided"

    source_full_path = source_path.resolve()

    # Clear error messages
    if not source_full_path.exists():
        raise FileNotFoundError(
            f"Import file not found: {file_path}\n"
            f"Resolved to: {source_full_path}\n"
            f"{resolution_context}"
        )

    if not source_full_path.is_file():
        raise ValueError(f"Path exists but is not a file: {source_full_path}")

    return source_full_path


def create_cli_processing_copy(
    source_file_path: str, file_id: str, source_type: str, config: ConfigProvider
) -> Path:
    """
    Create processing copy of CLI source file in app_processing directory.
    """
    from ..utils.paths import initialize_paths

    # Get paths system
    paths = initialize_paths(config)

    # Check if file path comes from CLI override (resolve from cwd) or config file (resolve from cli_source)
    resolve_from_cwd = (
        hasattr(config, "_cli_override")
        and config._cli_override
        and config._cli_override.get("file") == source_file_path
    )

    # Use enhanced validation to get source file location
    source_full_path = validate_import_file(
        source_file_path, config, resolve_from_cwd=resolve_from_cwd
    )

    # Create processing copy in source type subdirectory (same pattern as API)
    # file_id already includes cli_ prefix, so don't add it again
    processing_file_path = paths.app_processing / f"{source_type.lower()}" / file_id
    processing_file_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_full_path, processing_file_path)
    return processing_file_path


def get_import_settings(config: ConfigProvider) -> Tuple[str, str]:
    """
    Get import settings from configuration, with CLI argument override support.

    Returns:
        Tuple of (source_type, input_filename)
    """
    # Check for CLI overrides first
    if hasattr(config, "_cli_override") and config._cli_override:
        source_type = config._cli_override.get("type", "").lower()
        input_filename = config._cli_override.get("file", "")
        if source_type and input_filename:
            return source_type, input_filename

    # Fall back to config file settings
    cli_config = config.get_import_setting()
    if not cli_config:
        raise ValueError("No CLI import configuration found and no CLI arguments provided")

    source_type = cli_config.get("type", "").lower()
    input_filename = cli_config.get("file", "")

    if not source_type or not input_filename:
        raise ValueError("CLI import configuration missing required 'type' or 'file' fields")

    return source_type, input_filename


def monitor_cli_job(job_manager, job_id: str) -> int:
    """
    Monitor CLI job progress and display results.
    User can press CTRL-C to abort job.
    """
    print("Processing... (Press CTRL-C to abort job)")

    iteration = 0

    try:
        while True:
            try:
                job_status = job_manager.get_job_status(job_id)
                current_status = job_status.get("status", "UNKNOWN")

                # Debug: Show detailed status periodically (with newline to avoid interfering with logs)
                # if iteration % 10 == 0:
                #     print(f"\nStatus: {current_status}, Progress: {job_status.get('progress', 0)}%, Iteration: {iteration}")

                # Check for completion (use lowercase status values)
                if current_status in ["completed", "failed"]:
                    # Job completion status is shown in the NOTICE job summary below

                    # If failed due to abort, show abort message
                    if current_status == "failed":
                        error_msg = job_status.get("error_message", "")
                        if "aborted by user" in error_msg.lower():
                            print("Job was aborted by user.")
                            return 0

                    break

                # Don't exit on 100% progress - wait for actual completion status
                # Progress can reach 100% before final file writing is complete
                # Progress is now shown inline with "PROCESSING RECORD" messages
                time.sleep(1)
                iteration += 1

            except Exception as e:
                print(f"\nError monitoring job: {e}")
                return 1

    except KeyboardInterrupt:
        print("\n\n⏹️  CTRL-C received. Terminating process.")
        # Force immediate exit - terminate entire process including background threads
        import os

        os._exit(1)

    # Get final job status
    try:
        job_status = job_manager.get_job_status(job_id)
        if job_status["status"] == "completed":
            result = job_status["result"]
            logger.notice(f"{'═'*80}")
            logger.notice("📊 JOB SUMMARY")
            logger.notice(f"{'─'*60}")
            logger.notice("✅ Job completed successfully")
            logger.notice(f"🎯 Successful donations: {result['success_count']} records")
            logger.notice(f"❌ Failed donations: {result['fail_count']} records")
            logger.notice(f"📝 Success file: {result['success_file']}")
            logger.notice(f"📝 Fail file: {result['fail_file']}")
            logger.notice(f"📝 Log file: {result['log_file']}")
            logger.notice(f"{'═'*80}")
            return 0
        else:
            logger.error(f"❌ Job failed: {job_status.get('error_message', 'Unknown error')}")
            return 1
    except Exception as e:
        logger.error(f"❌ Error getting final job status: {e}")
        return 1


def run_cli_with_jobs(job_manager, config: ConfigProvider, oauth_tokens: Dict[str, Any]) -> int:
    """
    Run CLI import using job system infrastructure.
    """
    try:
        logger.info("CLI Job System Mode - Automated Processing")
        logger.info("=========================================")

        # Get import settings from config
        source_type, input_filename = get_import_settings(config)

        # Get OAuth configuration for nation slug
        oauth_config = config.get_oauth_config()
        nation_slug = oauth_config.get("slug", "") if oauth_config else ""

        # Confirmation prompt (like the original CLI)
        logger.notice(f"🚀 Starting {source_type.title()} Import")
        logger.notice(f"📁 Processing file: {input_filename}")
        logger.notice(f"🎯 NationBuilder environment: {nation_slug}")
        logger.notice(f"{'─'*40}")
        print()

        # Check if we're in an interactive terminal
        import sys

        if sys.stdin.isatty():
            try:
                input("Press Enter to continue, CTRL-C to abort...\n")
            except KeyboardInterrupt:
                print("Import cancelled by user.")
                return 1
        else:
            logger.info("Running in non-interactive mode - proceeding automatically...")

        # Generate job identifiers
        job_uuid = str(uuid.uuid4())
        file_id = f"{job_uuid}_cli_{Path(input_filename).name}"

        # Create processing copy in app_processing directory
        processing_file_path = create_cli_processing_copy(
            input_filename, file_id, source_type, config
        )
        logger.info(f"Processing copy created: {processing_file_path}")

        # Get hostname and IP for CLI machine tracking
        import socket

        cli_hostname = None
        cli_ip = None
        
        try:
            # Get the actual hostname
            cli_hostname = socket.gethostname()
            if cli_hostname in ["localhost", "localhost.localdomain"]:
                cli_hostname = None
        except Exception:
            pass

        try:
            # Get local IP address by connecting to a remote address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                cli_ip = s.getsockname()[0]
            finally:
                s.close()
        except Exception:
            pass

        # Get CLI version
        from .main import get_version
        cli_version = get_version()

        # Create machine info with available data
        machine_info = {
            "context": "cli",
            "cli_version": cli_version
        }
        if cli_hostname:
            machine_info["hostname"] = cli_hostname
        if cli_ip:
            machine_info["ip"] = cli_ip

        # Create job
        logger.info(f"Creating job from CLI machine: {machine_info}")
        job_id = job_manager.create_job(
            user_id="cli_user",
            nation_slug=nation_slug,
            file_id=file_id,
            storage_path=f"{source_type.lower()}/{file_id}",
            source_type=source_type,
            job_params={"cli_mode": True},
            oauth_tokens=oauth_tokens,  # Pass the obtained OAuth tokens
            machine_info=machine_info,  # Machine information with context
        )

        # Monitor job progress
        try:
            return monitor_cli_job(job_manager, job_id)
        finally:
            # Stop the job worker thread to allow CLI to exit cleanly
            logger.debug("Stopping job worker thread for CLI exit")
            job_manager.stop_worker()

    except FileNotFoundError as e:
        # Handle missing import files gracefully
        # Parse the detailed error message from validate_import_file
        error_msg = str(e)
        lines = error_msg.split('\n')
        
        # Log user-friendly error to both console and file
        logger.error("❌ Import file not found")
        for line in lines:
            if line.strip():
                logger.error(f"   {line.strip()}")
        
        logger.error("💡 Suggestions:")
        logger.error("   • Check that the file path in your config is correct")
        logger.error("   • Verify the file exists at the expected location")
        logger.error("   • Ensure you have read permissions for the file")
        return 1
    except Exception as e:
        logger.error(f"CLI job execution failed: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")
        return 1


def main():
    """Main entry point for import console script."""
    # Parse config file path and log level from command line arguments
    args = parse_arguments()
    config_path, log_level = args.config, args.log_level

    # Apply smart config path resolution
    from ..utils.config_paths import resolve_config_path

    resolved_config_path = resolve_config_path(config_path)

    # Initialize components with resolved config path and log level
    from ..utils.bootstrap import initialize_components_simplified

    config, logging_provider, app_log_path = initialize_components_simplified(
        config_path=str(resolved_config_path), console_log_level=log_level
    )

    # Apply CLI argument overrides to config if provided
    if hasattr(args, "type") and args.type:
        # Override config import settings with CLI arguments
        if not hasattr(config, "_cli_override"):
            config._cli_override = {}
        config._cli_override["type"] = args.type
    if hasattr(args, "file") and args.file:
        if not hasattr(config, "_cli_override"):
            config._cli_override = {}
        config._cli_override["file"] = args.file

    # Get logger from the initialized logging provider
    logger = logging_provider.get_logger(__name__)
    logger.info(f"CLI initialization complete. Logging to: {app_log_path}")

    return run_cli(config, logging_provider)


if __name__ == "__main__":
    # This allows the module to be run directly for testing
    sys.exit(run_cli())
