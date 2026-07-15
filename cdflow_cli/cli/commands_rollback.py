# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Command-line interface commands for donation rollback functionality.

This module provides the CLI interface for deleting donations and associated
people records that were previously imported through the donation import process.
"""

import os
import sys
import csv
import logging
import argparse
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, NamedTuple
from io import StringIO

from cdflow_cli.utils import start_fresh_output, clear_screen

from .command_bootstrap import STANDARD_LOG_LEVEL_CHOICES, initialize_cli_components
from .file_encoding import detect_file_encoding
from ..services.rollback_service import DonationRollbackService
from ..utils.menu import FileSelectionMenu
from ..utils.file_utils import safe_read_text_file

# Initialize module-level logger
logger = logging.getLogger(__name__)


class RollbackCliOptions(NamedTuple):
    success_file: Optional[str]
    output_dir: Optional[str]
    yes: bool


def resolve_success_file_path(selected_file: str, paths) -> Path:
    """Resolve an explicit or menu-selected success file to a concrete path."""
    candidate = Path(selected_file).expanduser()
    if candidate.is_absolute():
        return candidate

    matches = []
    cwd_candidate = (Path.cwd() / candidate).resolve()
    if cwd_candidate.exists():
        matches.append(cwd_candidate)

    if paths:
        output_candidate = (paths.output / candidate).resolve()
        if output_candidate.exists() and output_candidate not in matches:
            matches.append(output_candidate)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous success file path '{selected_file}'. Use an absolute path or a path unique to one location."
        )

    if paths:
        return (paths.output / candidate).resolve()
    return cwd_candidate


def resolve_output_directory(output_dir: Optional[str], paths) -> Path:
    """Resolve the output directory for rollback results."""
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    return paths.output


def get_encoding(file_path: str, paths=None) -> Tuple[str, float]:
    """
    Determine a file's encoding using paths system.

    Args:
        file_path: Path to the file
        paths: Paths system for file access

    Returns:
        Tuple of (encoding, confidence)
    """
    try:
        # Use paths system for file access
        if paths:
            if Path(file_path).is_absolute():
                full_file_path = Path(file_path)
            else:
                full_file_path = paths.output / file_path
        else:
            full_file_path = Path(file_path)

        return detect_file_encoding(full_file_path)
    except Exception as e:
        logger.error(f"Error detecting file encoding: {str(e)}")
        return "utf-8", 0.0  # Default to UTF-8 with low confidence


def get_success_csv_files(paths) -> List[str]:
    """
    Get list of *_success.csv files from output directory.

    Args:
        paths: Paths system

    Returns:
        List of success CSV file paths
    """
    try:
        if not paths or not paths.output.exists():
            logger.warning("Output directory not found or paths not available")
            return []

        success_files = list(paths.output.glob("*_success.csv"))
        if success_files:
            logger.debug(f"Found {len(success_files)} success files")
            return sorted([f.name for f in success_files])
        else:
            logger.debug("No success files found")
            return []

    except Exception as e:
        logger.error(f"Error listing success files: {str(e)}", exc_info=True)
        return []


def determine_import_type_from_header(header: str) -> Optional[str]:
    """
    Determine import type from CSV header line.

    Args:
        header: First line of CSV file

    Returns:
        'CanadaHelps', 'PayPal', or None if undetermined
    """
    if (
        "DONOR FIRST NAME" in header
        and "DONOR LAST NAME" in header
        and "DONOR EMAIL ADDRESS" in header
    ):
        return "CanadaHelps"
    elif "Name" in header and "From Email Address" in header and "Gross" in header:
        return "PayPal"
    else:
        return None


def initialize_output_file(
    filename: str, fieldnames: List[str], encoding: str, paths, output_dir: Optional[Path] = None
) -> None:
    """
    Initialize rollback output file with headers.

    Args:
        filename: Output filename
        fieldnames: CSV field names
        encoding: File encoding
        paths: Paths system
    """
    try:
        output_root = output_dir or paths.output
        output_file_path = output_root / filename
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create CSV content
        csv_output = StringIO()
        writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
        writer.writeheader()

        # Write to file - always use UTF-8 for output to handle Unicode characters
        output_file_path.write_text(csv_output.getvalue(), encoding="utf-8")
        logger.debug(f"Initialized output file: {output_file_path}")

    except Exception as e:
        logger.error(f"Failed to initialize output file: {str(e)}")
        raise


def append_row_to_file(
    filename: str,
    row: Dict[str, Any],
    fieldnames: List[str],
    encoding: str,
    paths,
    output_dir: Optional[Path] = None,
) -> None:
    """
    Append a row to the rollback output file.

    Args:
        filename: Output filename
        row: Row data to append
        fieldnames: CSV field names
        encoding: File encoding
        paths: Paths system
    """
    try:
        output_root = output_dir or paths.output
        output_file_path = output_root / filename

        # Create CSV content for this row
        csv_output = StringIO()
        writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
        writer.writerow(row)

        # Append to file - always use UTF-8 for output to handle Unicode characters
        with output_file_path.open("a", encoding="utf-8") as f:
            f.write(csv_output.getvalue())

    except Exception as e:
        logger.error(f"Failed to append row to file: {str(e)}")
        raise


def parse_rollback_arguments() -> RollbackCliOptions:
    """
    Parse command line arguments for rollback tool.

    Returns:
        RollbackCliOptions: Parsed rollback CLI options
    """
    parser = argparse.ArgumentParser(
        description="DonationFlow rollback donations from NationBuilder"
    )
    parser.add_argument("--config", nargs="?", help="Path to DonationFlow config YAML file")
    parser.add_argument("--success-file", help="Explicit success CSV to use for rollback")
    parser.add_argument("--output-dir", help="Directory to write rollback result CSVs to")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation prompts")
    args = parser.parse_args()
    return RollbackCliOptions(args.success_file, args.output_dir, args.yes)


def prompt_for_rollback_confirmation(
    nation_slug: str, selected_file: str, import_type: str
) -> bool:
    """
    Prompt user to confirm rollback operation.

    Args:
        nation_slug: NationBuilder nation slug
        selected_file: Selected file path
        import_type: Import type ('CanadaHelps' or 'PayPal')

    Returns:
        bool: True if confirmed, False otherwise
    """
    # clear_screen()
    start_fresh_output()
    print("\n")
    logger.info(f"{'═'*80}")
    logger.notice(
        f"⚠️  DANGER: Donations from {import_type} import will be DELETED from NationBuilder"
    )
    logger.info(f"{'─'*60}")
    logger.notice(f"📁 Processing file: {os.path.basename(selected_file)}")
    logger.notice(f"🎯 NationBuilder environment: {nation_slug}")
    logger.info(f"{'═'*80}")
    print("\n")

    try:
        input("Press Enter to continue, CTRL-C to abort...\n")
        return True
    except KeyboardInterrupt:
        logger.info("🚫 Rollback cancelled by user.")
        return False


def process_rollback_data(
    rows: List[Dict[str, Any]],
    import_type: str,
    rollback_service: DonationRollbackService,
    rollback_filename: str,
    reader_fieldnames: List[str],
    encoding: str,
    paths,
    logger,
    output_dir: Optional[Path] = None,
) -> Tuple[int, int]:
    """
    Process rollback data for donations - core business logic extracted for testability.
    
    Args:
        rows: List of CSV row dictionaries to process
        import_type: Import type ('CanadaHelps' or 'PayPal')
        rollback_service: Initialized rollback service instance
        rollback_filename: Output filename for results
        reader_fieldnames: CSV field names for output
        encoding: File encoding
        paths: Paths system instance
        logger: Logger instance
        
    Returns:
        Tuple[int, int]: (success_count, fail_count)
    """
    row_count = len(rows)
    success_count = 0
    fail_count = 0
    
    logger.notice(f"📊 Processing {row_count} donation records...")
    logger.info(f"{'═'*80}")
    
    # Process rows in reverse order (as per original logic)
    for row_index, row in enumerate(reversed(rows)):
        current_row = row_count - row_index
        logger.info(f"{'─'*60}")
        logger.info(f"🔄 Processing record {current_row} of {row_count}")

        # Process rollback for this row
        success, message = rollback_service.process_rollback_row(row, import_type)

        if success:
            success_count += 1
            logger.info(f"✅ Record {current_row} processed successfully")
        else:
            fail_count += 1
            logger.warning(f"❌ Record {current_row} failed: {message}")

        # Add error message to row and write to output
        row["NB Error Message"] = message
        append_row_to_file(rollback_filename, row, reader_fieldnames, encoding, paths, output_dir=output_dir)
    
    return success_count, fail_count


def run_rollback_cli(
    config=None,
    logging_provider=None,
    success_file: Optional[str] = None,
    output_dir: Optional[str] = None,
    auto_confirm: bool = False,
) -> int:
    """
    Run the command-line interface for donation rollback.

    Args:
        config: ConfigProvider instance (from bootstrap)
        logging_provider: Deprecated, ignored; logging is configured
            process-wide by configure_logging() during bootstrap

    Returns:
        int: Exit status code (0 for success, non-zero for errors)
    """
    logger = logging.getLogger(__name__)

    try:
        # Display startup message with formatting
        # clear_screen()
        start_fresh_output()
        print("\n")
        logger.notice("🚀 Launching DonationFlow Rollback Imported Donations...")
        logger.info(f"{'═'*80}")
        print("\n")

        # Initialize paths system
        from ..utils.paths import initialize_paths

        paths = initialize_paths(config)
        if not paths:
            logger.error("Failed to initialize paths system")
            return 1

        logger.notice("✅ DonationFlow Rollback initialization complete")
        logger.info(f"{'─'*60}")

        # Create rollback service
        rollback_service = DonationRollbackService(
            config_provider=config, logging_provider=logging_provider
        )

        # Initialize API clients
        logger.notice("🔐 Authenticating with NationBuilder...")
        if not rollback_service.initialize_api_clients():
            logger.error("❌ Failed to authenticate with NationBuilder. Exiting.")
            return 1
        logger.notice("✅ Authentication successful")

        if success_file:
            selected_file = success_file
            logger.notice(f"✅ Using explicit success file: {selected_file}")
        else:
            success_files = get_success_csv_files(paths)

            if not success_files:
                logger.error("❌ No _success.csv files found in output directory")
                return 1

            logger.notice(f"✅ Found {len(success_files)} success file(s)")
            logger.info(f"{'─'*60}")

            if not auto_confirm:
                input("Press Enter to continue, CTRL-C to abort...\n")

            menu = FileSelectionMenu(
                title="Select a CSV file to process:", file_pattern="*_success.csv"
            )

            selected_file = menu.show_menu(success_files)
            if not selected_file:
                logger.info("No file selected. Exiting.")
                return 1

        file_path = resolve_success_file_path(selected_file, paths)
        if not file_path.exists():
            logger.error(f"❌ Success file not found: {file_path}")
            return 1

        encoding, confidence = get_encoding(str(file_path), None)
        logger.debug(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")

        file_content = safe_read_text_file(file_path)
        first_line = file_content.split("\n")[0]

        # Determine import type
        import_type = determine_import_type_from_header(first_line)
        if not import_type:
            # Try to get from config as fallback
            import_config = config.get_import_setting()
            if import_config:
                source_type = import_config.get("type", "").lower()
                if source_type == "canadahelps":
                    import_type = "CanadaHelps"
                elif source_type == "paypal":
                    import_type = "PayPal"

            # Default to CanadaHelps if still undetermined
            if not import_type:
                import_type = "CanadaHelps"

        logger.notice(f"📋 File type detected: {import_type}")
        logger.notice(f"🎯 Target nation: {rollback_service.nation_slug}")
        logger.info(f"{'─'*60}")

        # Confirm rollback operation
        if auto_confirm:
            logger.notice("✅ Confirmation skipped via --yes")
        elif not prompt_for_rollback_confirmation(
            rollback_service.nation_slug, str(file_path), import_type
        ):
            return 1

        # Process the file
        csv_input = StringIO(file_content)
        reader = csv.DictReader(csv_input)
        rows = list(reader)
        row_count = len(rows)

        if row_count == 0:
            logger.warning("⚠️ No data rows found in file")
            return 1

        logger.notice(f"📊 Processing {row_count} donation records...")
        logger.info(f"{'═'*80}")

        # Generate rollback output file
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        rollback_filename = f"{file_path.stem}_rollback_{timestamp}.csv"
        resolved_output_dir = resolve_output_directory(output_dir, paths)

        # Initialize output file
        initialize_output_file(
            rollback_filename, reader.fieldnames, encoding, paths, output_dir=resolved_output_dir
        )
        logger.info(f"📝 Rollback results will be written to: {resolved_output_dir / rollback_filename}")
        logger.info(f"{'─'*60}")

        # Process the core rollback business logic (now extracted and testable)
        success_count, fail_count = process_rollback_data(
            rows=rows,
            import_type=import_type,
            rollback_service=rollback_service,
            rollback_filename=rollback_filename,
            reader_fieldnames=reader.fieldnames,
            encoding=encoding,
            paths=paths,
            logger=logger,
            output_dir=resolved_output_dir,
        )

        # Display summary with formatting
        logger.notice(f"{'═'*80}")
        logger.notice("📊 CLEANUP SUMMARY")
        logger.notice(f"{'─'*60}")

        if fail_count == 0:
            logger.notice(f"✅ Successfully processed all {row_count} records")
            logger.notice(f"🎯 Deleted: {success_count} donations")
            logger.notice(f"⚠️  Failed: {fail_count} donations")
        else:
            logger.notice(
                f"⚠️  Processed {row_count} rows with {success_count} successes and {fail_count} failures"
            )
            logger.notice(f"🎯 Deleted: {success_count} donations")
            logger.notice(f"❌ Failed: {fail_count} donations")

        logger.notice(f"📝 Results saved to: {rollback_filename}")
        logger.notice(f"{'═'*80}")
        return 0

    except Exception as e:
        logger.error(f"Unhandled exception in rollback CLI: {str(e)}", exc_info=True)
        return 1


def main(argv=None):
    """Main entry point for rollback console script."""
    import argparse

    parser = argparse.ArgumentParser(description="DonationFlow Rollback Tool")
    parser.add_argument(
        "--config", required=True, help="Path to configuration YAML file (required)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=STANDARD_LOG_LEVEL_CHOICES,
        help="Logging level",
    )
    parser.add_argument(
        "--success-file",
        help="Explicit success CSV to use for rollback (skips file discovery/menu)",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to write rollback result CSVs to (default: configured output path)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt once inputs are resolved",
    )
    parser.add_argument(
        "--log-os-log",
        action="store_true",
        help="Also send logs to macOS unified logging (Console.app)",
    )
    args = parser.parse_args(argv)

    try:
        config, logging_provider, app_log_path = initialize_cli_components(
            args.config,
            args.log_level,
            require_existing_config=True,
            os_log=getattr(args, "log_os_log", False),
        )
    except FileNotFoundError as exc:
        print(f"Configuration file not found: {exc}")
        return 1

    return run_rollback_cli(
        config,
        logging_provider,
        success_file=getattr(args, "success_file", None),
        output_dir=getattr(args, "output_dir", None),
        auto_confirm=getattr(args, "yes", False),
    )


if __name__ == "__main__":
    # This allows the module to be run directly for testing
    sys.exit(run_rollback_cli())
