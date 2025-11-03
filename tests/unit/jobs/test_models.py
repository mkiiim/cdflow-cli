import pytest
from cdflow_cli.jobs.models import JobStatus, JobResult, JobResponse, JobStatusResponse, FileUploadResponse


class TestJobStatus:
    """Test the JobStatus enum."""
    
    def test_job_status_values(self):
        """Test JobStatus enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        # Note: CANCELLED not defined in actual enum


class TestJobResult:
    """Test the JobResult Pydantic model."""
    
    def test_job_result_creation_defaults(self):
        """Test JobResult creation with default values."""
        result = JobResult()
        
        assert result.success_count == 0
        assert result.fail_count == 0
        assert result.total_count == 0
        assert result.success_file is None
        assert result.fail_file is None
        assert result.log_file is None
    
    def test_job_result_with_data(self):
        """Test JobResult creation with data."""
        result = JobResult(
            success_count=25,
            fail_count=2,
            total_count=27,
            success_file="success.csv",
            fail_file="failed.csv",
            log_file="import.log"
        )
        
        assert result.success_count == 25
        assert result.fail_count == 2
        assert result.total_count == 27
        assert result.success_file == "success.csv"
        assert result.fail_file == "failed.csv"
        assert result.log_file == "import.log"
    
    def test_job_result_json_serialization(self):
        """Test JobResult can be serialized to JSON."""
        result = JobResult(
            success_count=10,
            fail_count=1,
            total_count=11
        )
        
        json_dict = result.model_dump()
        assert json_dict['success_count'] == 10
        assert json_dict['fail_count'] == 1
        assert json_dict['total_count'] == 11


class TestJobResponse:
    """Test the JobResponse Pydantic model."""
    
    def test_job_response_creation(self):
        """Test JobResponse creation."""
        response = JobResponse(
            job_id="job-123",
            file_id="file-456",
            source_type="CanadaHelps",
            status=JobStatus.PENDING,
            created_at="2024-01-15T14:30:00Z",
            updated_at="2024-01-15T14:30:00Z"
        )
        
        assert response.job_id == "job-123"
        assert response.file_id == "file-456"
        assert response.source_type == "CanadaHelps"
        assert response.status == JobStatus.PENDING
        assert response.created_at == "2024-01-15T14:30:00Z"
        assert response.updated_at == "2024-01-15T14:30:00Z"


class TestJobStatusResponse:
    """Test the JobStatusResponse Pydantic model."""
    
    def test_job_status_response_minimal(self):
        """Test JobStatusResponse with minimal data."""
        response = JobStatusResponse(
            job_id="job-789",
            status=JobStatus.RUNNING,
            progress=45.5,
            created_at="2024-01-15T14:30:00Z",
            updated_at="2024-01-15T14:32:00Z"
        )
        
        assert response.job_id == "job-789"
        assert response.status == JobStatus.RUNNING
        assert response.progress == 45.5
        assert response.created_at == "2024-01-15T14:30:00Z"
        assert response.updated_at == "2024-01-15T14:32:00Z"
        assert response.queue_position is None
        assert response.result is None
    
    def test_job_status_response_with_result(self):
        """Test JobStatusResponse with job result."""
        job_result = JobResult(success_count=20, fail_count=0, total_count=20)
        response = JobStatusResponse(
            job_id="job-complete",
            status=JobStatus.COMPLETED,
            progress=100.0,
            created_at="2024-01-15T14:30:00Z",
            updated_at="2024-01-15T14:35:00Z",
            result=job_result
        )
        
        assert response.status == JobStatus.COMPLETED
        assert response.progress == 100.0
        assert response.result is not None
        assert response.result.success_count == 20


class TestFileUploadResponse:
    """Test the FileUploadResponse Pydantic model."""
    
    def test_file_upload_response_creation(self):
        """Test FileUploadResponse creation."""
        response = FileUploadResponse(
            file_id="file-abc123",
            original_filename="donations.csv",
            source_type="PayPal",
            storage_path="/storage/files/file-abc123.csv",
            upload_time="2024-01-15T14:30:00Z"
        )
        
        assert response.file_id == "file-abc123"
        assert response.original_filename == "donations.csv"
        assert response.source_type == "PayPal"
        assert response.storage_path == "/storage/files/file-abc123.csv"
        assert response.upload_time == "2024-01-15T14:30:00Z"