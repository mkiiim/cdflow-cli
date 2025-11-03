import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "nationbuilder": {
            "slug": "test-nation",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "redirect_uri": "http://localhost:8000/callback",
            "oauth": {
                "port": 8000,
                "timeout": 120
            }
        },
        "import": {
            "source": {
                "type": "canadahelps",
                "file_path": "donations.csv"
            },
            "processing": {
                "batch_size": 10,
                "rate_limit": 60,
                "dry_run": False
            }
        },
        "logging": {
            "level": "INFO"
        }
    }

@pytest.fixture
def sample_canadahelps_data():
    """Sample CanadaHelps CSV data."""
    return """ID,DONOR FIRST NAME,DONOR LAST NAME,DONOR EMAIL ADDRESS,AMOUNT,DONATION DATE,DONATION TIME,TRANSACTION NUMBER
1,John,Doe,test@example.com,25.00,2024-01-15,14:30:00,CH-123456
2,Jane,Smith,jane@example.com,50.00,2024-01-16,10:15:00,CH-789012
3,Bob,Johnson,bob@example.com,100.00,2024-01-17,16:45:00,CH-345678"""

@pytest.fixture
def sample_paypal_data():
    """Sample PayPal CSV data."""
    return """Date,Time,Name,Type,Status,Currency,Gross,Fee,Net,From Email Address,Transaction ID
15/01/2024,14:30:00,John Doe,Donation,Completed,CAD,25.00,1.25,23.75,test@example.com,PP-123456
16/01/2024,10:15:00,Jane Smith,Donation,Completed,CAD,50.00,2.50,47.50,jane@example.com,PP-789012
17/01/2024,16:45:00,Bob Johnson,Donation,Completed,CAD,100.00,5.00,95.00,bob@example.com,PP-345678"""

@pytest.fixture
def mock_nationbuilder_client():
    """Mock NationBuilder client for testing."""
    mock_client = Mock()
    mock_client.create_person.return_value = {"person": {"id": 123}}
    mock_client.create_donation.return_value = {"donation": {"id": 456}}
    mock_client.get_person.return_value = {"person": {"id": 123}}
    return mock_client