"""
Sample data fixtures for testing.
"""

SAMPLE_CANADAHELPS_CSV = """ID,DONOR FIRST NAME,DONOR LAST NAME,DONOR EMAIL ADDRESS,AMOUNT,DONATION DATE,DONATION TIME,TRANSACTION NUMBER,PROVINCE,POSTAL CODE,CAMPAIGN NAME
1,John,Doe,john@example.com,25.00,2024-01-15,14:30:00,CH-123456,ON,K1A 0A6,General Fund
2,Jane,Smith,jane@example.com,50.00,2024-01-16,15:45:00,CH-123457,BC,V6B 1A1,Monthly Giving
3,Bob,Johnson,bob@example.com,100.00,2024-01-17,16:15:00,CH-123458,AB,T2P 1A1,Special Campaign"""

SAMPLE_PAYPAL_CSV = """Date,Name,Type,Status,Currency,Amount,Fee,Net,From Email Address,Subject,Note
2024-01-15,John Doe,Donation,Completed,CAD,25.00,1.25,23.75,john@example.com,Monthly Donation,Keep up the great work!
2024-01-16,Jane Smith,Donation,Completed,CAD,50.00,2.50,47.50,jane@example.com,Annual Gift,
2024-01-17,Bob Johnson,Donation,Completed,CAD,100.00,5.00,95.00,bob@example.com,Special Support,Thank you for your work"""

SAMPLE_NATIONBUILDER_PERSON_RESPONSE = {
    "person": {
        "id": 123,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "created_at": "2024-01-15T14:30:00-05:00",
        "updated_at": "2024-01-15T14:30:00-05:00",
        "primary_address": {
            "state": "ON",
            "zip": "K1A 0A6"
        }
    }
}

SAMPLE_NATIONBUILDER_DONATION_RESPONSE = {
    "donation": {
        "id": 456,
        "amount_in_cents": 2500,
        "payment_type": "Credit Card",
        "donated_at": "2024-01-15T14:30:00-05:00",
        "person_id": 123,
        "tracking_code": "CH-123456",
        "created_at": "2024-01-15T14:30:00-05:00",
        "updated_at": "2024-01-15T14:30:00-05:00"
    }
}

SAMPLE_JOB_DATA = {
    "job_id": "test-job-123",
    "status": "completed",
    "created_at": "2024-01-15T14:00:00Z",
    "completed_at": "2024-01-15T14:30:00Z",
    "source_file": "donations.csv",
    "source_type": "canadahelps",
    "total_records": 3,
    "processed_records": 3,
    "failed_records": 0,
    "created_people": [
        {"person_id": 123, "email": "john@example.com"},
        {"person_id": 124, "email": "jane@example.com"},
        {"person_id": 125, "email": "bob@example.com"}
    ],
    "created_donations": [
        {"donation_id": 456, "person_id": 123, "amount": "25.00"},
        {"donation_id": 457, "person_id": 124, "amount": "50.00"},
        {"donation_id": 458, "person_id": 125, "amount": "100.00"}
    ],
    "errors": []
}

SAMPLE_CONFIG = {
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
    "rollback": {
        "job_id": "test-job-123",
        "confirm_deletion": False
    },
    "logging": {
        "level": "INFO",
        "file": "app.log"
    }
}