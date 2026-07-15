# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Dual-mode logging configuration built on structlog.

This module configures process-wide logging for the two ways cdflow-cli runs:

- "cli" mode: standalone command-line tool. Human-readable, coloured console
  output on stderr, with an optional rotating log file and an optional macOS
  unified logging (os_log) sink.
- "library" mode: imported by a host application (e.g. ccflow-app Celery
  tasks). JSON lines on stdout, with job context fields (job_id, user_id,
  nation_slug) merged into every record from a contextvars-based context.

Existing call sites keep using stdlib ``logging.getLogger(__name__)``;
structlog is wired in as the formatting layer via ProcessorFormatter.
"""

import contextvars
import logging
import logging.handlers
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

# Add custom NOTICE log level between WARNING(30) and ERROR(40)
NOTICE_LEVEL = 35
logging.addLevelName(NOTICE_LEVEL, "NOTICE")


def notice(self, message, *args, **kwargs):
    """Log at NOTICE level - important user-facing information"""
    if self.isEnabledFor(NOTICE_LEVEL):
        self._log(NOTICE_LEVEL, message, args, **kwargs)


# Add the method to Logger class
logging.Logger.notice = notice


DEFAULT_LOG_FILE_PATH = Path.home() / ".local" / "share" / "cdflow" / "cdflow.log"
DEFAULT_OS_LOG_SUBSYSTEM = "com.caestudy.cdflow"
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 3


_job_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "job_context", default={}
)


def bind_job_context(**kwargs) -> contextvars.Token:
    """
    Bind job context fields (e.g. job_id, user_id, nation_slug) for the
    current execution context. In library mode the bound fields are merged
    into every log record emitted from this context.

    Returns:
        contextvars.Token: Token to pass to reset_job_context() when done.
    """
    current = _job_context.get()
    return _job_context.set({**current, **kwargs})


def reset_job_context(token: contextvars.Token) -> None:
    """Restore the job context to its state before bind_job_context()."""
    _job_context.reset(token)


def get_job_context() -> Dict[str, Any]:
    """Return the currently bound job context fields."""
    return _job_context.get()


_current_log_file: Optional[Path] = None


def get_current_log_file() -> Optional[Path]:
    """
    Return the path of the rotating log file configured by the last
    configure_logging() call, or None when file logging is disabled.
    """
    return _current_log_file


def _resolve_level(level: Optional[str]) -> int:
    name = (level or "INFO").upper()
    if name == "NOTICE":
        return NOTICE_LEVEL
    resolved = getattr(logging, name, None)
    return resolved if isinstance(resolved, int) else logging.INFO


def _merge_job_context(logger, method_name, event_dict):
    """structlog processor: merge bound job context fields into the event."""
    for key, value in _job_context.get().items():
        event_dict.setdefault(key, value)
    return event_dict


def _build_pre_chain(mode: str):
    pre_chain = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if mode == "library":
        pre_chain.append(_merge_job_context)
    return pre_chain


def _console_renderer(colors: bool):
    level_styles = structlog.dev.ConsoleRenderer.get_default_level_styles(colors)
    if colors:
        level_styles["notice"] = "\x1b[1m"  # bold, distinct from info/warning
    return structlog.dev.ConsoleRenderer(colors=colors, level_styles=level_styles)


def _make_formatter(renderer, pre_chain, json_mode: bool = False):
    processors = [structlog.stdlib.ProcessorFormatter.remove_processors_meta]
    if json_mode:
        processors.append(structlog.processors.format_exc_info)
    processors.append(renderer)
    return structlog.stdlib.ProcessorFormatter(
        processors=processors,
        foreign_pre_chain=pre_chain,
    )


class OsLogHandler(logging.Handler):
    """
    Logging handler that forwards records to macOS unified logging (os_log).

    Records appear in Console.app under the configured subsystem, with the
    logger name as the category. macOS only; construction raises on other
    platforms or when the C runtime interface is unavailable.
    """

    _OS_LOG_TYPE_DEFAULT = 0x00
    _OS_LOG_TYPE_INFO = 0x01
    _OS_LOG_TYPE_DEBUG = 0x02
    _OS_LOG_TYPE_ERROR = 0x10
    _OS_LOG_TYPE_FAULT = 0x11

    def __init__(self, subsystem: str = DEFAULT_OS_LOG_SUBSYSTEM):
        super().__init__()
        if platform.system() != "Darwin":
            raise OSError("os_log is only available on macOS")

        import ctypes
        import ctypes.util

        self._ctypes = ctypes
        lib = ctypes.CDLL(ctypes.util.find_library("System"))

        lib.os_log_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.os_log_create.restype = ctypes.c_void_p

        # void _os_log_impl(void *dso, os_log_t log, os_log_type_t type,
        #                   const char *format, uint8_t *buf, uint32_t size)
        lib._os_log_impl.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint8,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_uint32,
        ]
        lib._os_log_impl.restype = None

        # _os_log_impl requires a valid image header as its dso anchor;
        # the main executable's header (image index 0) works for that.
        lib._dyld_get_image_header.argtypes = [ctypes.c_uint32]
        lib._dyld_get_image_header.restype = ctypes.c_void_p
        dso = lib._dyld_get_image_header(0)
        if not dso:
            raise OSError("could not resolve dso handle for os_log")

        self._lib = lib
        self._dso = dso
        self._subsystem = subsystem.encode("utf-8")
        self._logs: Dict[str, int] = {}

    def _log_object(self, category: str) -> int:
        log = self._logs.get(category)
        if log is None:
            log = self._lib.os_log_create(self._subsystem, category.encode("utf-8"))
            self._logs[category] = log
        return log

    def _os_log_type(self, levelno: int) -> int:
        if levelno >= logging.CRITICAL:
            return self._OS_LOG_TYPE_FAULT
        if levelno >= logging.ERROR:
            return self._OS_LOG_TYPE_ERROR
        if levelno >= logging.WARNING:
            return self._OS_LOG_TYPE_DEFAULT
        if levelno >= logging.INFO:
            return self._OS_LOG_TYPE_INFO
        return self._OS_LOG_TYPE_DEBUG

    def emit(self, record):
        try:
            ctypes = self._ctypes
            message = self.format(record).encode("utf-8", errors="replace")
            c_msg = ctypes.create_string_buffer(message)
            ptr = ctypes.cast(c_msg, ctypes.c_void_p).value
            # os_log argument buffer for a single %{public}s argument
            buf = (ctypes.c_uint8 * 12)()
            buf[0] = 0x02  # summary: has non-scalar arguments
            buf[1] = 0x01  # argument count
            buf[2] = 0x22  # descriptor: string, public
            buf[3] = 0x08  # argument length: pointer size
            for i in range(8):
                buf[4 + i] = (ptr >> (8 * i)) & 0xFF
            self._lib._os_log_impl(
                self._dso,
                self._log_object(record.name),
                self._os_log_type(record.levelno),
                b"%{public}s",
                buf,
                12,
            )
        except Exception:
            self.handleError(record)


def configure_logging(
    mode: str = "cli",
    level: str = "INFO",
    log_file: bool = False,
    log_file_path: Optional[Path] = None,
    file_level: str = "DEBUG",
    os_log: bool = False,
    os_log_subsystem: str = DEFAULT_OS_LOG_SUBSYSTEM,
) -> None:
    """
    Configure process-wide logging. Call once at process startup.

    Args:
        mode: "cli" for human-readable console output, "library" for JSON
            lines on stdout with job context fields merged in.
        level: Console (cli) / stdout (library) log level; supports NOTICE.
        log_file: cli mode only - enable the rotating log file.
        log_file_path: Rotating log file location; defaults to
            ~/.local/share/cdflow/cdflow.log.
        file_level: cli mode only - rotating log file level.
        os_log: cli mode only - also send records to macOS unified logging.
        os_log_subsystem: Subsystem shown in Console.app.
    """
    global _current_log_file

    if mode not in ("cli", "library"):
        raise ValueError(f"Unsupported logging mode: {mode}")

    pre_chain = _build_pre_chain(mode)
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    _current_log_file = None

    if mode == "library":
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(_resolve_level(level))
        stream_handler.setFormatter(
            _make_formatter(structlog.processors.JSONRenderer(), pre_chain, json_mode=True)
        )
        root.addHandler(stream_handler)
        root.setLevel(_resolve_level(level))
    else:
        console_level = _resolve_level(level)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(_make_formatter(_console_renderer(colors=True), pre_chain))
        root.addHandler(console_handler)
        effective_level = console_level

        if log_file:
            path = Path(log_file_path) if log_file_path else DEFAULT_LOG_FILE_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                path,
                maxBytes=LOG_FILE_MAX_BYTES,
                backupCount=LOG_FILE_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_level_value = _resolve_level(file_level)
            file_handler.setLevel(file_level_value)
            file_handler.setFormatter(
                _make_formatter(_console_renderer(colors=False), pre_chain)
            )
            root.addHandler(file_handler)
            _current_log_file = path
            effective_level = min(effective_level, file_level_value)

        if os_log:
            if platform.system() == "Darwin":
                try:
                    os_log_handler = OsLogHandler(os_log_subsystem)
                    os_log_handler.setLevel(console_level)
                    root.addHandler(os_log_handler)
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        f"os_log sink unavailable, continuing without it: {e}"
                    )
            else:
                logging.getLogger(__name__).warning(
                    "os_log sink requested but only supported on macOS, ignoring"
                )

        root.setLevel(effective_level)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
