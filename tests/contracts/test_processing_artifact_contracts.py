from unittest.mock import Mock, patch

from cdflow_cli.cli.commands_rollback import process_rollback_data
from cdflow_cli.jobs.extractor import ImportLogExtractor
from cdflow_cli.services.import_service import DonationImportService


class TestImportArtifactContracts:
    """Behavior-first contracts for import artifact generation and output rows."""

    def test_generate_output_filenames_use_import_prefix_and_input_stem(self):
        mock_config = Mock()
        mock_config.get_logging_config.return_value = {"file_level": "DEBUG", "console_level": "INFO"}

        mock_paths = Mock()

        with patch("cdflow_cli.services.import_service.get_paths", return_value=mock_paths):
            with patch("cdflow_cli.services.import_service.get_logging_provider", return_value=Mock()):
                service = DonationImportService(config_provider=mock_config)

        service.now_str = "20260404-105551"
        log_name, success_name, fail_name = service.generate_output_filenames(
            "paypal/monthly-giving.csv", output_dir=Mock()
        )

        assert log_name == "IMPORTDONATIONS_20260404-105551_monthly-giving.log"
        assert success_name == "IMPORTDONATIONS_20260404-105551_monthly-giving_success.csv"
        assert fail_name == "IMPORTDONATIONS_20260404-105551_monthly-giving_fail.csv"

    def test_append_row_to_file_omits_plugin_only_fields(self, tmp_path):
        mock_config = Mock()
        mock_config.get_logging_config.return_value = {"file_level": "DEBUG", "console_level": "INFO"}

        mock_paths = Mock()
        mock_paths.output = tmp_path

        with patch("cdflow_cli.services.import_service.get_paths", return_value=mock_paths):
            with patch("cdflow_cli.services.import_service.get_logging_provider", return_value=Mock()):
                service = DonationImportService(config_provider=mock_config)

        filename = "artifact.csv"
        fieldnames = ["Name", "Email", "Amount"]

        service._initialize_output_file(filename, fieldnames, "utf-8")
        service._append_row_to_file(
            filename,
            {
                "Name": "Jane Doe",
                "Email": "jane@example.com",
                "Amount": "25.00",
                "_tracking_code": "ignored",
                "_skip_row": False,
            },
            fieldnames,
            "utf-8",
        )

        content = (tmp_path / filename).read_text(encoding="utf-8")
        assert "Jane Doe" in content
        assert "jane@example.com" in content
        assert "25.00" in content
        assert "_tracking_code" not in content
        assert "ignored" not in content

    def test_run_import_returns_false_when_input_contract_is_missing(self):
        mock_config = Mock()
        mock_config.get_logging_config.return_value = {"file_level": "DEBUG", "console_level": "INFO"}

        mock_paths = Mock()

        with patch("cdflow_cli.services.import_service.get_paths", return_value=mock_paths):
            with patch("cdflow_cli.services.import_service.get_logging_provider", return_value=Mock()):
                service = DonationImportService(config_provider=mock_config)

        with patch.object(service, "determine_input_file", return_value=(None, None, None)):
            success, success_count, fail_count = service.run_import()

        assert success is False
        assert success_count == 0
        assert fail_count == 0

    def test_job_side_import_log_name_keeps_import_prefix_timestamp_and_job_id(self):
        extractor = ImportLogExtractor.__new__(ImportLogExtractor)

        filename = extractor._generate_import_log_filename(
            job_id="job-123",
            start_time="2026-04-04T10:55:51Z",
            original_filename="uploads/monthly-giving.csv",
        )

        assert filename == "IMPORTDONATIONS_20260404-105551_job-123_monthly-giving.log"

    def test_extractor_prefers_explicit_job_owned_log_filename(self):
        extractor = ImportLogExtractor.__new__(ImportLogExtractor)
        extractor.logging_provider = Mock()

        filename = extractor._get_current_api_log_file("APP_20260404_105551.log")

        assert filename == "APP_20260404_105551.log"


class TestRollbackArtifactContracts:
    """Behavior-first contracts for rollback core processing."""

    def test_process_rollback_data_reverses_rows_and_writes_messages(self):
        rows = [
            {"NB Donation ID": "1", "Email": "first@example.com"},
            {"NB Donation ID": "2", "Email": "second@example.com"},
        ]
        mock_service = Mock()
        mock_service.process_rollback_row.side_effect = [
            (True, "SUCCESS delete_donation :: 2"),
            (False, "FAILURE delete_donation :: 1"),
        ]

        with patch("cdflow_cli.cli.commands_rollback.append_row_to_file") as mock_append:
            success_count, fail_count = process_rollback_data(
                rows=rows,
                import_type="CanadaHelps",
                rollback_service=mock_service,
                rollback_filename="rollback.csv",
                reader_fieldnames=["NB Donation ID", "Email", "NB Error Message"],
                encoding="utf-8",
                paths=Mock(),
                logger=Mock(),
            )

        assert success_count == 1
        assert fail_count == 1

        first_processed_row = mock_service.process_rollback_row.call_args_list[0][0][0]
        second_processed_row = mock_service.process_rollback_row.call_args_list[1][0][0]
        assert first_processed_row["Email"] == "second@example.com"
        assert second_processed_row["Email"] == "first@example.com"

        written_rows = [call_args[0][1] for call_args in mock_append.call_args_list]
        assert written_rows[0]["NB Error Message"] == "SUCCESS delete_donation :: 2"
        assert written_rows[1]["NB Error Message"] == "FAILURE delete_donation :: 1"
