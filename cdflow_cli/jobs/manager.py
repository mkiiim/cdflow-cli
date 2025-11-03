# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Background job processing for DonationFlow CLI API.

This module provides functionality for running donation import jobs
as background tasks, with progress tracking and result reporting.
"""

import json
import logging
import threading
import queue
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from ..utils.config import ConfigProvider
from ..utils.file_utils import safe_read_text_file
from ..utils.logging import LoggingProvider
from ..utils.paths import get_paths
from .extractor import ImportLogExtractor
from ..services.import_service import DonationImportService
from .models import JobStatus, JobResult

# Initialize module-level logger
logger = logging.getLogger(__name__)

# Job queue for background processing
job_queue = queue.Queue()

# Dictionary to store job status and results
jobs_store = {}


class JobManager:
    """
    Manager for job processing and tracking.

    This class handles the creation, execution, and tracking of
    donation import jobs running in the background.
    """

    def __init__(self, config_provider: ConfigProvider, logging_provider: LoggingProvider):
        """
        Initialize the job manager.

        Args:
            config_provider: Configuration provider
            logging_provider: Logging provider
        """
        self.config_provider = config_provider
        self.logging_provider = logging_provider

        # Initialize paths system for direct Path operations
        try:
            self.paths = get_paths()
            logger.debug("Paths system available for job operations")
        except Exception as e:
            logger.warning(f"Paths system not available: {e}")
            self.paths = None
        self.job_thread = None
        self.active = False
        self._job_lock = threading.RLock()  # Thread safety for job status updates

        # Initialize log extractor for import log separation
        try:
            self.log_extractor = ImportLogExtractor(config_provider, logging_provider)
        except Exception as e:
            logger.warning(f"Failed to initialize log extractor: {str(e)}")
            self.log_extractor = None

        logger.debug("JobManager initialized")

    def start_worker(self):
        """
        Start the background worker thread for processing jobs.
        """
        if self.job_thread is not None and self.job_thread.is_alive():
            logger.debug("Worker thread already running")
            return

        self.active = True
        self.job_thread = threading.Thread(target=self._process_jobs)
        self.job_thread.daemon = False  # Non-daemon thread survives CLI process exit
        self.job_thread.start()

        logger.info("Started background job worker thread")

    def stop_worker(self):
        """
        Stop the background worker thread.
        """
        self.active = False
        if self.job_thread is not None:
            self.job_thread.join(timeout=5.0)
            logger.info("Stopped background job worker thread")

    def abort_job(self, job_id: str) -> bool:
        """
        Abort a running job.

        Args:
            job_id: ID of the job to abort

        Returns:
            bool: True if job was aborted, False if job not found or already completed
        """
        with self._job_lock:
            # Get the job
            job = self.get_job_status(job_id)
            if not job:
                logger.error(f"Cannot abort unknown job {job_id}")
                return False

            current_status = job.get("status", "UNKNOWN")

            # Only abort jobs that are pending or running
            if current_status not in ["pending", "running"]:
                logger.info(f"Job {job_id} is {current_status}, cannot abort")
                return False

            # Mark job as failed with abort message
            self._update_job_status(
                job_id,
                JobStatus.FAILED,
                job.get("progress", 0),
                error_message="Job aborted by user",
            )

            logger.info(f"Job {job_id} marked as aborted")
            return True

    def _process_jobs(self):
        """
        Process jobs from the queue in the background.
        """
        logger.debug("Job worker thread started")

        while self.active:
            try:
                # Get a job from the queue, wait up to 1 second
                try:
                    job = job_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                logger.info(f"Processing job {job['job_id']}")

                # Record when processing actually started
                processing_started_at = datetime.now().isoformat()

                # Update job status to RUNNING and record processing start time
                self._update_job_status(
                    job["job_id"], JobStatus.RUNNING, 0, processing_started_at=processing_started_at
                )

                # Get file path
                file_path = job["storage_path"]

                try:
                    # Initialize import service with job context for tracking
                    import_service = DonationImportService(
                        config_provider=self.config_provider, 
                        logging_provider=self.logging_provider,
                        job_context=job  # Pass full job context for donation tracking
                    )

                    # Check if we have OAuth tokens from the user session
                    oauth_tokens = job.get("oauth_tokens")
                    if oauth_tokens:
                        # Use pre-authenticated tokens instead of interactive OAuth
                        if not import_service.initialize_api_clients_with_tokens(oauth_tokens):
                            raise Exception("Failed to initialize API clients with user tokens")
                    else:
                        # Fallback to standard initialization (for backward compatibility)
                        if not import_service.initialize_api_clients():
                            raise Exception("Failed to initialize API clients")

                    # Track the total count for final result
                    csv_total_count = 0

                    # Set up progress callback with abort checking
                    def progress_callback(
                        progress, status_message=None, success_count=0, fail_count=0, total_count=0
                    ):
                        nonlocal csv_total_count

                        # Check if job has been aborted
                        current_job = self.get_job_status(job["job_id"])
                        if (
                            current_job
                            and current_job.get("status") == "failed"
                            and "aborted by user" in current_job.get("error_message", "").lower()
                        ):
                            raise Exception("Job aborted by user")

                        # Capture the total count from CSV for final result
                        if total_count > csv_total_count:
                            csv_total_count = total_count

                        # Create a partial result with current counts
                        partial_result = None
                        if success_count > 0 or fail_count > 0 or total_count > 0:
                            partial_result = JobResult(
                                success_count=success_count,
                                fail_count=fail_count,
                                total_count=total_count,
                                success_file=None,
                                fail_file=None,
                                log_file=None,
                            )

                        self._update_job_status(
                            job["job_id"],
                            JobStatus.RUNNING,
                            progress,
                            status_message,
                            partial_result,
                        )

                    # Read file to determine encoding
                    # This is a simplification - in a real impl you might use chardet
                    # encoding = 'utf-8'
                    # Get encoding from job parameters if available
                    encoding = "utf-8"  # Default encoding
                    if "job_params" in job and job["job_params"].get("file_encoding"):
                        encoding = job["job_params"]["file_encoding"]
                        logger.debug(f"Using provided encoding: {encoding}")

                    # Run the import
                    success, success_count, fail_count = import_service.run_import(
                        input_filename=file_path,
                        encoding=encoding,
                        source_type=job["source_type"],
                        progress_callback=progress_callback,
                    )

                    # Get output file paths
                    # We'd need to modify DonationImportService to return these
                    output_dir = Path(".")
                    log_filename, success_filename, fail_filename = (
                        import_service.get_output_filenames(
                            input_filename=file_path, output_dir=output_dir
                        )
                    )

                    # Create result using the CSV total count for consistency
                    final_total_count = (
                        csv_total_count if csv_total_count > 0 else success_count + fail_count
                    )
                    result = JobResult(
                        success_count=success_count,
                        fail_count=fail_count,
                        total_count=final_total_count,
                        success_file=success_filename,
                        fail_file=fail_filename,
                        log_file=log_filename,
                    )

                    logger.info(
                        f"Job {job['job_id']} final counts: success={success_count}, fail={fail_count}, total_csv_rows={csv_total_count}, final_total={final_total_count}"
                    )

                    # Update job status to COMPLETED
                    self._update_job_status(
                        job["job_id"],
                        JobStatus.COMPLETED if success else JobStatus.FAILED,
                        100,
                        result=result,
                    )

                    logger.info(
                        f"Job {job['job_id']} completed with {success_count} successes and {fail_count} failures"
                    )

                    # Extract import-specific logs after job completion
                    # Get updated job record with processing_started_at field
                    updated_job = self.get_job_status(job["job_id"])
                    if updated_job:
                        self._extract_import_logs_for_job(updated_job)
                    else:
                        logger.warning(
                            f"Could not retrieve updated job record for {job['job_id']}, skipping log extraction"
                        )

                except Exception as e:
                    logger.error(f"Error processing job {job['job_id']}: {str(e)}")

                    # Update job status to FAILED
                    self._update_job_status(
                        job["job_id"], JobStatus.FAILED, 0, error_message=str(e)
                    )

                finally:
                    # Mark the job as done in the queue
                    job_queue.task_done()

            except Exception as e:
                logger.error(f"Unexpected error in job worker: {str(e)}")

    def create_job(
        self,
        user_id: str,
        nation_slug: str,
        file_id: str,
        storage_path: str,
        source_type: str,
        job_params: Dict[str, Any] = None,
        api_log_filename: str = None,
        oauth_tokens: Dict[str, Any] = None,
        machine_info: Dict[str, Any] = None,
    ) -> str:
        """
        Create a new import job.

        Args:
            user_id: ID of the user creating the job
            file_id: ID of the file to process
            storage_path: Path to the file in storage
            source_type: Source type (CanadaHelps or PayPal)
            job_params: Additional job parameters (e.g., file_encoding)
            api_log_filename: Name of the API log file for this session
            oauth_tokens: OAuth tokens from authenticated user session
            machine_info: Machine information (hostname, IP, context) where job was created

        Returns:
            str: ID of the created job
        """
        # Extract UUID from file_id to use as job_id (eliminates dual-ID system)
        # file_id format: "{uuid}_{original_filename}" or "{uuid}_cli_{original_filename}"
        parts = file_id.split("_")
        if len(parts) >= 3 and parts[1] == "cli":
            # CLI job: include cli_ prefix in job_id
            job_id = f"{parts[0]}_cli"
        else:
            # API job: use just the UUID
            job_id = parts[0]

        # Create the job record
        job = {
            "job_id": job_id,
            "file_id": file_id,
            "storage_path": storage_path,
            "source_type": source_type,
            "status": JobStatus.PENDING.value,
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "nation_slug": nation_slug,
            "result": None,
            "error_message": None,
            "job_params": job_params or {},  # Store additional job parameters
            "api_log_filename": api_log_filename,  # Reference to the API log file for this session
            "oauth_tokens": oauth_tokens,  # Store OAuth tokens from authenticated user
            "machine_info": machine_info or {},  # Store machine information (hostname, IP, context)
        }

        # Save the job to the store and file
        jobs_store[job_id] = job
        self._save_job_to_file(job)

        # Add the job to the queue
        job_queue.put(job)

        # Ensure the worker is running
        self.start_worker()

        logger.notice(f"Created job {job_id} for file {file_id}")
        return job_id

    def _sanitize_job_data(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize job data by removing sensitive information like OAuth tokens.

        Args:
            job_data: Raw job data

        Returns:
            dict: Sanitized job data safe for API responses
        """
        sanitized = job_data.copy()

        # Remove OAuth tokens for security
        if "oauth_tokens" in sanitized:
            del sanitized["oauth_tokens"]

        return sanitized

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a job.

        Args:
            job_id: ID of the job

        Returns:
            dict or None: Job status information, or None if job not found
        """
        with self._job_lock:
            # Check memory store first
            if job_id in jobs_store:
                job_data = jobs_store[job_id].copy()

                # Add queue position for pending jobs
                if job_data.get("status") == JobStatus.PENDING.value:
                    job_data["queue_position"] = self._get_queue_position(job_id)

                # Sanitize before returning
                return self._sanitize_job_data(job_data)

            # If not in memory, try to load from file
            # job_path = f"jobs/{job_id}.json"
            job_path = f"{job_id}.json"

            # Check if job file exists using paths system
            job_file_path = self.paths.jobs / job_path
            file_exists = job_file_path.exists()
            job_content = None

            if file_exists:
                job_content = safe_read_text_file(job_file_path)
                logger.debug(f"Read job file using paths system: {job_file_path}")

            if file_exists and job_content:
                try:
                    job = json.loads(job_content)

                    # Cache in memory for future lookups
                    jobs_store[job_id] = job

                    # Add queue position for pending jobs
                    if job.get("status") == JobStatus.PENDING.value:
                        job["queue_position"] = self._get_queue_position(job_id)

                    # Sanitize before returning
                    return self._sanitize_job_data(job)
                except Exception as e:
                    logger.error(f"Error loading job {job_id} from file: {str(e)}")

            return None

    def _get_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get the position of a job in the queue.

        Args:
            job_id: ID of the job

        Returns:
            int or None: 1-based position in queue, or None if not in queue
        """
        try:
            # Convert queue to list to inspect contents
            # Note: This creates a temporary list without removing items from queue
            queue_items = []
            temp_queue = queue.Queue()

            # Extract all items from queue
            while not job_queue.empty():
                try:
                    item = job_queue.get_nowait()
                    queue_items.append(item)
                    temp_queue.put(item)
                except queue.Empty:
                    break

            # Put items back in the queue
            while not temp_queue.empty():
                try:
                    item = temp_queue.get_nowait()
                    job_queue.put(item)
                except queue.Empty:
                    break

            # Find the position of the job
            for i, job in enumerate(queue_items):
                if job.get("job_id") == job_id:
                    return i + 1  # 1-based position

            return None

        except Exception as e:
            logger.error(f"Error getting queue position for job {job_id}: {str(e)}")
            return None

    def list_jobs_for_user(self, user_id: str, nation_slug: str) -> List[Dict[str, Any]]:
        """
        List all jobs for a user.

        Args:
            user_id: ID of the user

        Returns:
            list: List of job records
        """
        jobs = []

        # Get all job files using paths system
        job_files = []

        # Use direct Path operations
        jobs_dir_path = self.paths.jobs
        if jobs_dir_path.exists() and jobs_dir_path.is_dir():
            try:
                # List all JSON files in the jobs directory
                job_files = [f.name for f in jobs_dir_path.glob("*.json")]
                logger.debug(f"Found {len(job_files)} job files using paths system")
            except Exception as e:
                logger.error(f"Error listing job files with paths system: {str(e)}")

        # Process each job file
        for job_path in job_files:
            try:
                # Read and parse the job file using paths system
                job_file_path = self.paths.jobs / job_path
                job_content = None

                if job_file_path.exists():
                    job_content = safe_read_text_file(job_file_path)
                    logger.debug(f"Read job file using paths system: {job_file_path}")

                if job_content:
                    job = json.loads(job_content)

                    # Only include jobs for this user
                    if job.get("user_id") == user_id and job.get("nation_slug") == nation_slug:
                        # Sanitize job data before adding to list
                        sanitized_job = self._sanitize_job_data(job)
                        jobs.append(sanitized_job)

                        # Cache original job (with tokens) in memory for internal use
                        jobs_store[job["job_id"]] = job
            except Exception as e:
                logger.error(f"Error loading job from {job_path}: {str(e)}")

        return jobs

    def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float,
        status_message: Optional[str] = None,
        result: Optional[JobResult] = None,
        error_message: Optional[str] = None,
        processing_started_at: Optional[str] = None,
    ):
        """
        Update the status of a job.

        Args:
            job_id: ID of the job
            status: New status
            progress: Progress percentage (0-100)
            status_message: Optional status message
            result: Optional result data (for completed jobs)
            error_message: Optional error message (for failed jobs)
            processing_started_at: Optional timestamp when job processing actually started
        """
        with self._job_lock:
            # Get the job
            job = self.get_job_status(job_id)
            if not job:
                logger.error(f"Cannot update status for unknown job {job_id}")
                return

            # Update the job
            job["status"] = status.value
            job["progress"] = progress
            job["updated_at"] = datetime.now().isoformat()

            if status_message is not None:
                job["status_message"] = status_message

            if result is not None:
                job["result"] = result.dict()

            if error_message is not None:
                job["error_message"] = error_message

            if processing_started_at is not None:
                job["processing_started_at"] = processing_started_at

            # Save updates to file first, then memory store (for atomicity)
            try:
                self._save_job_to_file(job)
                jobs_store[job_id] = job
                logger.debug(f"Updated job {job_id} status to {status.value}, progress: {progress}")
            except Exception as e:
                logger.error(f"Failed to update job {job_id} status: {str(e)}")
                # Don't update memory if file save failed
                raise

    def _save_job_to_file(self, job: Dict[str, Any]):
        """
        Save a job record to a file.

        Args:
            job: Job record to save
        """
        job_path = f"{job['job_id']}.json"
        try:
            job_content = json.dumps(job, indent=2)

            # Use direct Path operations
            job_file_path = self.paths.jobs / job_path
            job_file_path.parent.mkdir(parents=True, exist_ok=True)
            job_file_path.write_text(job_content, encoding="utf-8")

            # Verify the write was successful
            if not job_file_path.exists():
                raise Exception("File write verification failed - file does not exist after write")

            logger.debug(f"Saved job file using paths system: {job_file_path}")

        except Exception as e:
            logger.error(f"Error saving job {job['job_id']} to file: {str(e)}")
            raise  # Re-raise to trigger rollback in _update_job_status

    def _extract_import_logs_for_job(self, job: Dict[str, Any]) -> None:
        """
        Extract import-specific logs for a completed job.

        Args:
            job: Job record containing job details
        """
        if not self.log_extractor:
            logger.debug(
                f"Log extractor not available, skipping extraction for job {job['job_id']}"
            )
            return

        try:
            # Calculate end time (current time since job just completed)
            end_time = datetime.now().isoformat()

            # Extract original filename from file_id if available
            original_filename = None
            if "file_id" in job:
                # file_id format: "{uuid}_{original_filename}" or "{uuid}_cli_{original_filename}"
                parts = job["file_id"].split("_")
                if len(parts) >= 3 and parts[1] == "cli":
                    # CLI job: skip the cli part and join the rest
                    original_filename = "_".join(parts[2:])
                elif len(parts) > 1:
                    # API job: everything after the first underscore
                    original_filename = "_".join(parts[1:])

            # Use processing_started_at if available, otherwise fall back to created_at
            start_time = job.get("processing_started_at", job["created_at"])

            if "processing_started_at" in job:
                logger.debug(f"Using processing start time for log extraction: {start_time}")
            else:
                logger.debug(
                    f"Using creation time for log extraction (processing_started_at not available): {start_time}"
                )

            # Extract import logs using actual processing start time
            import_log_path = self.log_extractor.extract_import_log(
                job_id=job["job_id"],
                start_time=start_time,
                end_time=end_time,
                original_filename=original_filename,
            )

            # Update job result with the actual import log path
            if "result" in job and job["result"]:
                # Update the log_file in the result to point to extracted log
                with self._job_lock:
                    job["result"]["log_file"] = import_log_path
                    job["updated_at"] = datetime.now().isoformat()

                    # Save updated job record
                    self._save_job_to_file(job)

                    # Update in-memory store
                    jobs_store[job["job_id"]] = job

            logger.debug(
                f"Successfully extracted import log for job {job['job_id']}: {import_log_path}"
            )

        except Exception as e:
            # Log extraction failure should not fail the job
            logger.warning(f"Failed to extract import log for job {job['job_id']}: {str(e)}")
            # Continue without failing the job - extraction is supplementary
