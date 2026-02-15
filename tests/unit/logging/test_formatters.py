"""Tests for log formatters."""

import json
import logging
import sys

from src.logging.context import clear_context, set_correlation_id, set_extra_context
from src.logging.formatters import HumanFormatter, JSONFormatter


def _make_record(message="test message", level=logging.INFO):
    """Create a test log record."""
    return logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="test.py",
        lineno=42,
        msg=message,
        args=(),
        exc_info=None,
    )


class TestJSONFormatter:
    def setup_method(self):
        clear_context()

    def test_outputs_valid_json(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_includes_message(self):
        formatter = JSONFormatter()
        record = _make_record("hello world")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"

    def test_includes_level(self):
        formatter = JSONFormatter()
        record = _make_record(level=logging.ERROR)
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"

    def test_includes_timestamp(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed

    def test_excludes_timestamp_when_disabled(self):
        formatter = JSONFormatter(include_timestamp=False)
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" not in parsed

    def test_includes_service_name(self):
        formatter = JSONFormatter(service_name="my-service")
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["service"] == "my-service"

    def test_includes_location(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["line"] == 42

    def test_excludes_location_when_disabled(self):
        formatter = JSONFormatter(include_location=False)
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "line" not in parsed

    def test_includes_correlation_id(self):
        set_correlation_id("corr-123")
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "corr-123"

    def test_includes_extra_context(self):
        set_extra_context(mission_id="m-001")
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["mission_id"] == "m-001"

    def test_includes_exception_info(self):
        formatter = JSONFormatter()
        record = _make_record()
        try:
            raise ValueError("test error")  # noqa: TRY301
        except ValueError:
            record.exc_info = sys.exc_info()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "test error"


class TestHumanFormatter:
    def setup_method(self):
        clear_context()

    def test_outputs_pipe_separated(self):
        formatter = HumanFormatter(use_colors=False)
        record = _make_record()
        output = formatter.format(record)
        assert "|" in output

    def test_includes_message(self):
        formatter = HumanFormatter(use_colors=False)
        record = _make_record("hello world")
        output = formatter.format(record)
        assert "hello world" in output

    def test_includes_level(self):
        formatter = HumanFormatter(use_colors=False)
        record = _make_record(level=logging.WARNING)
        output = formatter.format(record)
        assert "WARNING" in output

    def test_colors_enabled(self):
        formatter = HumanFormatter(use_colors=True)
        record = _make_record()
        output = formatter.format(record)
        assert "\033[" in output

    def test_truncates_long_logger_name(self):
        formatter = HumanFormatter(use_colors=False)
        record = _make_record()
        record.name = "very.long.module.name.that.exceeds.the.maximum.length"
        output = formatter.format(record)
        assert "..." in output

    def test_includes_correlation_id(self):
        set_correlation_id("corr-abc")
        formatter = HumanFormatter(use_colors=False)
        record = _make_record()
        output = formatter.format(record)
        assert "corr-abc" in output
