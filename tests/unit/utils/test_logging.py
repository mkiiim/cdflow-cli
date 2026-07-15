# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Tests for the structlog-based dual-mode logging configuration.
"""

import io
import json
import logging

import pytest

from cdflow_cli.utils.logging import (
    NOTICE_LEVEL,
    bind_job_context,
    configure_logging,
    get_current_log_file,
    get_job_context,
    reset_job_context,
)


@pytest.fixture(autouse=True)
def restore_root_logger():
    """Snapshot and restore root logger handlers around each test."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    yield
    for handler in logging.getLogger().handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)


def _capture_handler_output(handler_index=0):
    """Swap the stream of a root StreamHandler for a StringIO and return it."""
    root = logging.getLogger()
    stream = io.StringIO()
    root.handlers[handler_index].stream = stream
    return stream


class TestNoticeLevel:
    def test_notice_level_registered(self):
        assert NOTICE_LEVEL == 35
        assert logging.getLevelName(NOTICE_LEVEL) == "NOTICE"

    def test_logger_notice_method(self):
        configure_logging(mode="cli", level="NOTICE")
        stream = _capture_handler_output()

        test_logger = logging.getLogger("cdflow_cli.test_notice")
        test_logger.info("info suppressed")
        test_logger.notice("notice visible")

        output = stream.getvalue()
        assert "notice visible" in output
        assert "info suppressed" not in output


class TestJobContext:
    def test_bind_get_reset_roundtrip(self):
        token = bind_job_context(job_id="job-1", user_id=42)
        assert get_job_context() == {"job_id": "job-1", "user_id": 42}

        nested = bind_job_context(nation_slug="demo")
        assert get_job_context() == {
            "job_id": "job-1",
            "user_id": 42,
            "nation_slug": "demo",
        }

        reset_job_context(nested)
        assert get_job_context() == {"job_id": "job-1", "user_id": 42}
        reset_job_context(token)
        assert get_job_context() == {}


class TestCliMode:
    def test_console_only_by_default(self):
        configure_logging(mode="cli", level="INFO")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert get_current_log_file() is None

    def test_rotating_file_sink(self, tmp_path):
        log_path = tmp_path / "cdflow.log"
        configure_logging(
            mode="cli", level="ERROR", log_file=True, log_file_path=log_path
        )
        assert get_current_log_file() == log_path

        test_logger = logging.getLogger("cdflow_cli.test_file")
        test_logger.info("file only line")

        contents = log_path.read_text()
        assert "file only line" in contents

    def test_file_level_independent_of_console_level(self, tmp_path):
        log_path = tmp_path / "cdflow.log"
        configure_logging(
            mode="cli",
            level="ERROR",
            log_file=True,
            log_file_path=log_path,
            file_level="DEBUG",
        )
        stream = _capture_handler_output()

        test_logger = logging.getLogger("cdflow_cli.test_levels")
        test_logger.debug("debug line")

        assert "debug line" in log_path.read_text()
        assert "debug line" not in stream.getvalue()

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError):
            configure_logging(mode="server")


class TestLibraryMode:
    def _configured_json_stream(self, level="INFO"):
        configure_logging(mode="library", level=level)
        return _capture_handler_output()

    def test_json_lines_on_single_handler(self):
        stream = self._configured_json_stream()
        assert len(logging.getLogger().handlers) == 1
        assert get_current_log_file() is None

        logging.getLogger("cdflow_cli.test_json").info("hello %s", "world")

        record = json.loads(stream.getvalue().strip())
        assert record["event"] == "hello world"
        assert record["level"] == "info"
        assert record["logger"] == "cdflow_cli.test_json"
        assert "timestamp" in record

    def test_job_context_merged_into_records(self):
        stream = self._configured_json_stream()
        token = bind_job_context(job_id="job-9", user_id=7, nation_slug="demo")
        try:
            logging.getLogger("cdflow_cli.test_ctx").info("with context")
        finally:
            reset_job_context(token)
        logging.getLogger("cdflow_cli.test_ctx").info("without context")

        lines = [json.loads(line) for line in stream.getvalue().strip().splitlines()]
        assert lines[0]["job_id"] == "job-9"
        assert lines[0]["user_id"] == 7
        assert lines[0]["nation_slug"] == "demo"
        assert "job_id" not in lines[1]

    def test_notice_level_serialized(self):
        stream = self._configured_json_stream()
        logging.getLogger("cdflow_cli.test_notice_json").notice("summary")

        record = json.loads(stream.getvalue().strip())
        assert record["level"] == "notice"

    def test_exceptions_serialized_as_text(self):
        stream = self._configured_json_stream()
        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("cdflow_cli.test_exc").error("failed", exc_info=True)

        record = json.loads(stream.getvalue().strip())
        assert "ValueError: boom" in record["exception"]
