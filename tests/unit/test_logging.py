"""Tests for configure_logging() — dual renderer, JSONL output, required fields."""

# tests/unit/test_logging.py
import json
import logging
from pathlib import Path

import pytest
import structlog

from app.core.log_events import LogEvent


@pytest.fixture(autouse=True)
def reset_logging_config(monkeypatch):
    """Ensure _CONFIGURED=False and log level=DEBUG before each test.

    Two things leak across the process without this:
      1. structlog/_CONFIGURED + stdlib handlers from earlier tests.
      2. LOG_LEVEL resolved from the active .env.test profile — if that
         profile sets WARNING or higher, configure_logging() sets the root
         logger to that level and every logger.info() call here is silently
         dropped before reaching any handler, producing an empty log file.

    Rather than trust the env/dotenv resolution chain to land on DEBUG,
    stub _log_level() directly — this test file is about the logging
    pipeline, not about Settings precedence.
    """
    import app.core.logging as log_mod
    from app.core.config import reset_settings

    def _reset() -> None:
        log_mod._CONFIGURED = False
        structlog.reset_defaults()
        logging.disable(logging.NOTSET)
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
            h.close()
        root.setLevel(logging.NOTSET)

    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setattr(log_mod, "_log_level", lambda: logging.DEBUG)
    reset_settings()
    _reset()
    yield
    _reset()
    reset_settings()


def _flush() -> None:
    """Flush all root logger handlers before reading log file."""
    for h in logging.getLogger().handlers:
        h.flush()


def _make_jsonl_file(tmp_path: Path) -> Path:
    return tmp_path / "api.jsonl"


def test_configure_logging_is_idempotent(tmp_path):
    """configure_logging called twice — only one handler added."""
    from app.core.logging import configure_logging

    log_file = _make_jsonl_file(tmp_path)
    configure_logging("api", log_file=str(log_file))
    handler_count = len(logging.getLogger().handlers)

    configure_logging("api", log_file=str(log_file))
    assert len(logging.getLogger().handlers) == handler_count


def test_file_output_is_valid_jsonl(tmp_path):
    """Each log call writes one valid JSON object per line to the JSONL file."""
    from app.core.logging import configure_logging, get_logger

    log_file = _make_jsonl_file(tmp_path)
    configure_logging("api", log_file=str(log_file))

    logger = get_logger("test")
    logger.info(LogEvent.SONG_SUBMITTED, song_id="abc123")
    logger.info(LogEvent.TASK_DONE, task_id="t1")
    _flush()

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert isinstance(obj, dict)


def test_required_fields_present_in_jsonl(tmp_path):
    """Every JSONL line has: timestamp, level, event, service, trace_id."""
    from app.core.logging import configure_logging, get_logger

    log_file = _make_jsonl_file(tmp_path)
    configure_logging("api", log_file=str(log_file))

    get_logger("test").info(LogEvent.HEALTH_CHECKED)
    _flush()

    obj = json.loads(log_file.read_text().strip().splitlines()[0])

    assert "timestamp" in obj
    assert "level" in obj
    assert "event" in obj
    assert "service" in obj
    assert "trace_id" in obj


def test_service_field_matches_configure_arg(tmp_path):
    """service field in JSONL equals the name passed to configure_logging."""
    from app.core.logging import configure_logging, get_logger

    log_file = _make_jsonl_file(tmp_path)
    configure_logging("worker", log_file=str(log_file))

    get_logger("test").info(LogEvent.TASK_RECEIVED)
    _flush()

    obj = json.loads(log_file.read_text().strip())
    assert obj["service"] == "worker"


def test_trace_id_is_unknown_without_otel_context(tmp_path):
    """trace_id defaults to 'unknown' when no OTEL span is active."""
    from app.core.logging import configure_logging, get_logger

    log_file = _make_jsonl_file(tmp_path)
    configure_logging("api", log_file=str(log_file))

    get_logger("test").info(LogEvent.REQUEST_STARTED)
    _flush()

    obj = json.loads(log_file.read_text().strip())
    assert obj["trace_id"] == "unknown"


def test_event_field_uses_log_event_value(tmp_path):
    """event field in JSONL matches LogEvent.value (lowercase snake_case)."""
    from app.core.logging import configure_logging, get_logger

    log_file = _make_jsonl_file(tmp_path)
    configure_logging("api", log_file=str(log_file))

    get_logger("test").info(LogEvent.DOWNLOAD_STARTED, song_id="x")
    _flush()

    obj = json.loads(log_file.read_text().strip())
    assert obj["event"] == LogEvent.DOWNLOAD_STARTED.value
