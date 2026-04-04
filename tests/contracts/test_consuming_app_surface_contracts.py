from pathlib import Path
from unittest.mock import Mock, patch

from cdflow_cli.adapters.nationbuilder.oauth import NationBuilderOAuth
from cdflow_cli.jobs import JobArtifact, JobManager, JobResult, JobStatus
from cdflow_cli.services.auth_service import AuthContext, UnifiedAuthService
from cdflow_cli.utils.bootstrap import initialize_components_simplified
from cdflow_cli.utils.config import ConfigProvider
from cdflow_cli.utils.file_utils import safe_read_text_file
from cdflow_cli.utils.logging import LoggingProvider, get_logging_provider
from cdflow_cli.utils.paths import initialize_paths


class TestConsumingAppSurfaceContracts:
    """Behavior-first contracts for Python surfaces imported by cflow-app-preprod."""

    def test_consuming_app_imported_symbols_are_available(self):
        assert ConfigProvider.__name__ == "ConfigProvider"
        assert LoggingProvider.__name__ == "LoggingProvider"
        assert callable(get_logging_provider)
        assert callable(safe_read_text_file)
        assert JobManager.__name__ == "JobManager"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobResult.__name__ == "JobResult"
        assert JobArtifact.__name__ == "JobArtifact"
        assert callable(initialize_paths)
        assert callable(initialize_components_simplified)
        assert NationBuilderOAuth.__name__ == "NationBuilderOAuth"
        assert UnifiedAuthService.__name__ == "UnifiedAuthService"
        assert AuthContext.API.value == "api"

    def test_initialize_components_simplified_returns_current_three_value_tuple(self, tmp_path):
        config = Mock(spec=ConfigProvider)
        config.get_logging_config.return_value = {"file_level": "DEBUG", "console_level": "INFO"}

        paths = Mock()
        paths.logs = tmp_path / "logs"

        logging_provider = Mock(spec=LoggingProvider)
        logging_provider.get_logger.return_value = Mock()

        with patch("cdflow_cli.utils.bootstrap.ConfigProvider", return_value=config):
            with patch("cdflow_cli.utils.bootstrap.initialize_paths", return_value=paths):
                with patch(
                    "cdflow_cli.utils.bootstrap.get_logging_provider",
                    return_value=logging_provider,
                ):
                    result = initialize_components_simplified(
                        config_path="/tmp/config.yaml",
                        console_log_level="NOTICE",
                    )

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[0] is config
        assert result[1] is logging_provider
        assert Path(result[2]).parent == paths.logs

        logging_provider.configure_logging.assert_called_once()
        _, kwargs = logging_provider.configure_logging.call_args
        assert kwargs["log_level"] == "DEBUG"
        assert kwargs["early_init"] is True
        assert kwargs["log_filename"].startswith("APP_")

    def test_job_result_exposes_consuming_app_artifact_fields(self):
        result = JobResult(
            success_count=4,
            fail_count=1,
            total_count=5,
            success_file="job-123_success.csv",
            fail_file="job-123_fail.csv",
            log_file="IMPORTDONATIONS_20260404-105551_job-123.log",
            artifacts={
                "success": JobArtifact(
                    path="job-123_success.csv",
                    storage_root="output",
                    display_name="job-123_success.csv",
                    kind="success_output",
                )
            },
        )

        assert result.success_file == "job-123_success.csv"
        assert result.fail_file == "job-123_fail.csv"
        assert result.log_file == "IMPORTDONATIONS_20260404-105551_job-123.log"
        assert result.artifacts["success"].path == "job-123_success.csv"
