# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
API data models for DonationFlow CLI.

This module defines the Pydantic models used for request and response objects
in the API layer, providing schema validation and documentation.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Enum representing the status of a donation import job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FileUploadResponse(BaseModel):
    """Response model for file upload endpoint."""

    file_id: str = Field(..., description="Unique identifier for the uploaded file")
    original_filename: str = Field(..., description="Original filename as uploaded by the user")
    source_type: str = Field(..., description="Source type (CanadaHelps or PayPal)")
    storage_path: str = Field(..., description="Storage path where the file is saved")
    upload_time: str = Field(..., description="Timestamp when the file was uploaded")


class JobResult(BaseModel):
    """Model representing the result of a completed job."""

    success_count: int = Field(0, description="Number of successfully imported donations")
    fail_count: int = Field(0, description="Number of failed imports")
    total_count: int = Field(0, description="Total number of records to process")
    success_file: Optional[str] = Field(None, description="Path to the success output file")
    fail_file: Optional[str] = Field(None, description="Path to the failed records output file")
    log_file: Optional[str] = Field(None, description="Path to the log file")


class JobResponse(BaseModel):
    """Response model for job creation and job listing."""

    job_id: str = Field(..., description="Unique identifier for the job")
    file_id: str = Field(..., description="Identifier of the file being processed")
    source_type: str = Field(..., description="Source type (CanadaHelps or PayPal)")
    status: JobStatus = Field(..., description="Current status of the job")
    created_at: str = Field(..., description="Timestamp when the job was created")
    updated_at: str = Field(..., description="Timestamp when the job was last updated")


class JobStatusResponse(BaseModel):
    """Response model for job status endpoint."""

    job_id: str = Field(..., description="Unique identifier for the job")
    status: JobStatus = Field(..., description="Current status of the job")
    progress: float = Field(..., description="Progress percentage (0-100)")
    created_at: str = Field(..., description="Timestamp when the job was created")
    updated_at: str = Field(..., description="Timestamp when the job was last updated")
    queue_position: Optional[int] = Field(
        None, description="Position in queue (1-based, only for pending jobs)"
    )
    result: Optional[JobResult] = Field(
        None, description="Result data (available when job is completed)"
    )
