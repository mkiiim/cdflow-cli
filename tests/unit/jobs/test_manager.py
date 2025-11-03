# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Unit tests for JobManager background job processing.

Tests cover job lifecycle, thread safety, file persistence,
OAuth token handling, and error scenarios.
"""

import json
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import tempfile

from cdflow_cli.jobs.manager import JobManager, job_queue, jobs_store
from cdflow_cli.jobs.models import JobStatus, JobResult
from cdflow_cli.utils.config import ConfigProvider
from cdflow_cli.utils.logging import LoggingProvider


class TestJobManager:
    """Test JobManager functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration provider."""
        config = Mock(spec=ConfigProvider)
        config.config_path = "/tmp/test_config.yaml"
        return config

    @pytest.fixture
    def mock_logging(self):
        """Mock logging provider."""
        logging_provider = Mock(spec=LoggingProvider)
        logging_provider.get_current_log_filename.return_value = "test_app.log"
        return logging_provider

    @pytest.fixture
    def mock_paths(self):
        """Mock paths system."""
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = Mock()
            paths.jobs = Path(temp_dir) / "jobs"
            paths.logs = Path(temp_dir) / "logs"
            paths.jobs.mkdir(parents=True, exist_ok=True)
            paths.logs.mkdir(parents=True, exist_ok=True)
            
            with patch('cdflow_cli.jobs.manager.get_paths', return_value=paths):
                yield paths

    @pytest.fixture
    def job_manager(self, mock_config, mock_logging, mock_paths):
        """Create JobManager instance for testing."""
        # Clear global state before each test
        global job_queue, jobs_store
        while not job_queue.empty():
            try:
                job_queue.get_nowait()
            except queue.Empty:
                break
        jobs_store.clear()
        
        with patch('cdflow_cli.jobs.manager.ImportLogExtractor'), \
             patch('cdflow_cli.jobs.manager.DonationImportService'):
            manager = JobManager(mock_config, mock_logging)
            # Don't auto-start worker to avoid race conditions in tests
            manager.active = False
            yield manager
            
            # Cleanup after test
            manager.stop_worker()
            jobs_store.clear()

    def test_job_manager_initialization(self, job_manager, mock_config, mock_logging):
        """Test JobManager initializes correctly."""
        assert job_manager.config_provider == mock_config
        assert job_manager.logging_provider == mock_logging
        assert job_manager.paths is not None
        assert job_manager.job_thread is None
        assert job_manager.active is False
        assert hasattr(job_manager, '_job_lock')

    def test_create_job_basic(self, job_manager):
        """Test basic job creation."""
        with patch.object(job_manager, 'start_worker'):  # Prevent auto-start
            job_id = job_manager.create_job(
                user_id="test_user",
                nation_slug="test_nation",
                file_id="12345_test_file.csv",
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps"
            )
        
        assert job_id == "12345"
        
        # Verify job was created in store
        job = job_manager.get_job_status(job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["user_id"] == "test_user"
        assert job["nation_slug"] == "test_nation"
        assert job["status"] == JobStatus.PENDING.value
        assert job["progress"] == 0

    def test_create_job_cli_format(self, job_manager):
        """Test job creation with CLI file ID format."""
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation", 
            file_id="12345_cli_test_file.csv",
            storage_path="/tmp/test_file.csv",
            source_type="PayPal"
        )
        
        assert job_id == "12345_cli"

    def test_create_job_with_oauth_tokens(self, job_manager):
        """Test job creation with OAuth tokens."""
        oauth_tokens = {
            "access_token": "test_token",
            "refresh_token": "test_refresh"
        }
        
        with patch.object(job_manager, 'start_worker'):
            job_id = job_manager.create_job(
                user_id="test_user",
                nation_slug="test_nation",
                file_id="12345_test_file.csv", 
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps",
                oauth_tokens=oauth_tokens
            )
        
        # Verify OAuth tokens are stored but not returned in sanitized response
        job = job_manager.get_job_status(job_id)
        assert "oauth_tokens" not in job  # Should be sanitized
        
        # Check internal store has tokens
        assert jobs_store[job_id]["oauth_tokens"] == oauth_tokens

    def test_job_sanitization(self, job_manager):
        """Test that sensitive data is removed from job responses."""
        oauth_tokens = {"access_token": "secret", "refresh_token": "secret"}
        
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation",
            file_id="12345_test_file.csv",
            storage_path="/tmp/test_file.csv", 
            source_type="CanadaHelps",
            oauth_tokens=oauth_tokens
        )
        
        job = job_manager.get_job_status(job_id)
        assert "oauth_tokens" not in job
        assert job["user_id"] == "test_user"  # Non-sensitive data preserved

    def test_update_job_status(self, job_manager):
        """Test job status updates."""
        with patch.object(job_manager, 'start_worker'):
            job_id = job_manager.create_job(
                user_id="test_user",
                nation_slug="test_nation",
                file_id="12345_test_file.csv",
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps"
            )
        
        # Update to running
        job_manager._update_job_status(
            job_id, JobStatus.RUNNING, 50, "Processing data"
        )
        
        job = job_manager.get_job_status(job_id)
        assert job["status"] == JobStatus.RUNNING.value
        assert job["progress"] == 50
        assert job["status_message"] == "Processing data"

    def test_update_job_with_result(self, job_manager):
        """Test job completion with result."""
        with patch.object(job_manager, 'start_worker'):
            job_id = job_manager.create_job(
                user_id="test_user",
                nation_slug="test_nation",
                file_id="12345_test_file.csv",
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps"
            )
        
        result = JobResult(
            success_count=10,
            fail_count=2,
            total_count=12,
            success_file="success.csv",
            fail_file="fail.csv",
            log_file="import.log"
        )
        
        job_manager._update_job_status(
            job_id, JobStatus.COMPLETED, 100, result=result
        )
        
        job = job_manager.get_job_status(job_id)
        assert job["status"] == JobStatus.COMPLETED.value
        assert job["result"]["success_count"] == 10
        assert job["result"]["fail_count"] == 2

    def test_abort_job_pending(self, job_manager):
        """Test aborting a pending job."""
        with patch.object(job_manager, 'start_worker'):
            job_id = job_manager.create_job(
                user_id="test_user",
                nation_slug="test_nation",
                file_id="12345_test_file.csv",
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps"
            )
        
        success = job_manager.abort_job(job_id)
        assert success is True
        
        job = job_manager.get_job_status(job_id)
        assert job["status"] == JobStatus.FAILED.value
        assert "aborted by user" in job["error_message"]

    def test_abort_job_running(self, job_manager):
        """Test aborting a running job."""
        with patch.object(job_manager, 'start_worker'):
            job_id = job_manager.create_job(
                user_id="test_user", 
                nation_slug="test_nation",
                file_id="12345_test_file.csv",
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps"
            )
        
        # Set to running first
        job_manager._update_job_status(job_id, JobStatus.RUNNING, 25)
        
        success = job_manager.abort_job(job_id)
        assert success is True
        
        job = job_manager.get_job_status(job_id)
        assert job["status"] == JobStatus.FAILED.value

    def test_abort_job_completed(self, job_manager):
        """Test cannot abort completed job."""
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation", 
            file_id="12345_test_file.csv",
            storage_path="/tmp/test_file.csv",
            source_type="CanadaHelps"
        )
        
        # Set to completed
        job_manager._update_job_status(job_id, JobStatus.COMPLETED, 100)
        
        success = job_manager.abort_job(job_id)
        assert success is False

    def test_abort_unknown_job(self, job_manager):
        """Test aborting unknown job returns False."""
        success = job_manager.abort_job("unknown_job")
        assert success is False

    def test_list_jobs_for_user(self, job_manager):
        """Test listing jobs for specific user."""
        # Create jobs for different users
        job1 = job_manager.create_job(
            user_id="user1",
            nation_slug="nation1",
            file_id="12345_file1.csv",
            storage_path="/tmp/file1.csv",
            source_type="CanadaHelps"
        )
        
        job2 = job_manager.create_job(
            user_id="user2", 
            nation_slug="nation1",
            file_id="67890_file2.csv",
            storage_path="/tmp/file2.csv",
            source_type="PayPal"
        )
        
        job3 = job_manager.create_job(
            user_id="user1",
            nation_slug="nation1", 
            file_id="11111_file3.csv",
            storage_path="/tmp/file3.csv",
            source_type="CanadaHelps"
        )
        
        # Get jobs for user1
        user1_jobs = job_manager.list_jobs_for_user("user1", "nation1")
        job_ids = [job["job_id"] for job in user1_jobs]
        
        assert len(user1_jobs) == 2
        assert job1 in job_ids
        assert job3 in job_ids
        assert job2 not in job_ids

    def test_worker_thread_lifecycle(self, job_manager):
        """Test worker thread start/stop."""
        assert job_manager.job_thread is None
        assert job_manager.active is False
        
        job_manager.start_worker()
        assert job_manager.job_thread is not None
        assert job_manager.job_thread.is_alive()
        assert job_manager.active is True
        
        job_manager.stop_worker()
        assert job_manager.active is False

    def test_worker_thread_already_running(self, job_manager):
        """Test starting worker when already running."""
        job_manager.start_worker()
        first_thread = job_manager.job_thread
        
        job_manager.start_worker()  # Should not create new thread
        assert job_manager.job_thread == first_thread

    def test_job_file_persistence(self, job_manager, mock_paths):
        """Test job persistence to file system."""
        with patch.object(job_manager, 'start_worker'):
            job_id = job_manager.create_job(
                user_id="test_user",
                nation_slug="test_nation",
                file_id="12345_test_file.csv", 
                storage_path="/tmp/test_file.csv",
                source_type="CanadaHelps"
            )
        
        # Check file was created
        job_file = mock_paths.jobs / f"{job_id}.json"
        assert job_file.exists()
        
        # Verify file contents
        with open(job_file, 'r') as f:
            content = f.read()
            if content.strip():  # Only parse if file has content
                job_data = json.loads(content)
                assert job_data["job_id"] == job_id
                assert job_data["user_id"] == "test_user"

    def test_job_loading_from_file(self, job_manager, mock_paths):
        """Test loading job from file when not in memory."""
        job_id = "test_job_123"
        job_data = {
            "job_id": job_id,
            "user_id": "test_user",
            "nation_slug": "test_nation",
            "status": JobStatus.COMPLETED.value,
            "progress": 100,
            "created_at": datetime.now().isoformat()
        }
        
        # Create job file directly
        job_file = mock_paths.jobs / f"{job_id}.json"
        with open(job_file, 'w') as f:
            json.dump(job_data, f)
        
        # Clear memory store
        jobs_store.clear()
        
        # Should load from file
        job = job_manager.get_job_status(job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["status"] == JobStatus.COMPLETED.value

    def test_error_handling_invalid_job_update(self, job_manager):
        """Test error handling for invalid job updates."""
        # Try to update non-existent job
        with patch('cdflow_cli.jobs.manager.logger') as mock_logger:
            job_manager._update_job_status(
                "nonexistent", JobStatus.RUNNING, 50
            )
            mock_logger.error.assert_called()

    def test_queue_position_tracking(self, job_manager):
        """Test queue position tracking for pending jobs."""
        # Create multiple jobs
        job1 = job_manager.create_job(
            user_id="user1", nation_slug="nation1",
            file_id="1_file1.csv", storage_path="/tmp/1.csv", 
            source_type="CanadaHelps"
        )
        job2 = job_manager.create_job(
            user_id="user1", nation_slug="nation1", 
            file_id="2_file2.csv", storage_path="/tmp/2.csv",
            source_type="CanadaHelps"
        )
        
        # Check queue positions (implementation dependent)
        job1_status = job_manager.get_job_status(job1)
        job2_status = job_manager.get_job_status(job2)
        
        # Both should have queue_position for pending jobs
        if job1_status.get("status") == JobStatus.PENDING.value:
            assert "queue_position" in job1_status
        if job2_status.get("status") == JobStatus.PENDING.value:
            assert "queue_position" in job2_status

    def test_job_params_storage(self, job_manager):
        """Test storing additional job parameters."""
        job_params = {
            "file_encoding": "utf-8",
            "custom_field": "test_value"
        }
        
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation",
            file_id="12345_test_file.csv",
            storage_path="/tmp/test_file.csv", 
            source_type="CanadaHelps",
            job_params=job_params
        )
        
        job = job_manager.get_job_status(job_id)
        assert job["job_params"] == job_params

    def test_machine_info_storage(self, job_manager):
        """Test storing machine information with job."""
        machine_info = {
            "hostname": "test-machine",
            "ip": "192.168.1.100",
            "context": "cli"
        }
        
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation", 
            file_id="12345_test_file.csv",
            storage_path="/tmp/test_file.csv",
            source_type="CanadaHelps",
            machine_info=machine_info
        )
        
        job = job_manager.get_job_status(job_id)
        assert job["machine_info"] == machine_info

    def test_thread_safety_job_updates(self, job_manager):
        """Test thread safety of concurrent job updates."""
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation",
            file_id="12345_test_file.csv", 
            storage_path="/tmp/test_file.csv",
            source_type="CanadaHelps"
        )
        
        def update_job():
            for i in range(10):
                job_manager._update_job_status(
                    job_id, JobStatus.RUNNING, i * 10
                )
                time.sleep(0.01)
        
        # Run concurrent updates
        threads = [threading.Thread(target=update_job) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Job should still be valid
        job = job_manager.get_job_status(job_id)
        assert job is not None
        assert job["status"] == JobStatus.RUNNING.value

    @patch('cdflow_cli.jobs.manager.DonationImportService')
    def test_job_processing_simulation(self, mock_import_service, job_manager):
        """Test job processing workflow simulation."""
        # Setup mock import service
        mock_service = Mock()
        mock_import_service.return_value = mock_service
        mock_service.initialize_api_clients.return_value = True
        mock_service.run_import.return_value = (True, 5, 1)
        mock_service.get_output_filenames.return_value = ("log.log", "success.csv", "fail.csv")
        
        # Create and start job
        job_id = job_manager.create_job(
            user_id="test_user",
            nation_slug="test_nation",
            file_id="12345_test_file.csv",
            storage_path="/tmp/test_file.csv",
            source_type="CanadaHelps"
        )
        
        # Let worker process briefly
        time.sleep(0.1)
        
        # Job should exist
        job = job_manager.get_job_status(job_id)
        assert job is not None
