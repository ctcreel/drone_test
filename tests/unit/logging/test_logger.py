"""Tests for logging setup and logger factory."""

import io
import logging

from src.logging.config import LogFormat, LoggingConfig, LogLevel
from src.logging.logger import get_logger, reset_logging, setup_logging


class TestSetupLogging:
    def setup_method(self):
        reset_logging()

    def test_configures_root_logger(self):
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_json_format_by_default(self):
        stream = io.StringIO()
        setup_logging(stream=stream)
        logger = get_logger("test")
        logger.info("test message")
        output = stream.getvalue()
        assert "{" in output

    def test_human_format(self):
        config = LoggingConfig(log_format=LogFormat.HUMAN)
        stream = io.StringIO()
        setup_logging(config=config, stream=stream)
        logger = get_logger("test")
        logger.info("test message")
        output = stream.getvalue()
        assert "|" in output

    def test_idempotent_without_force(self):
        setup_logging()
        root = logging.getLogger()
        handler_count = len(root.handlers)
        setup_logging()
        assert len(root.handlers) == handler_count

    def test_force_reconfigures(self):
        setup_logging()
        setup_logging(force=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1

    def test_respects_log_level(self):
        config = LoggingConfig(log_level=LogLevel.ERROR)
        setup_logging(config=config)
        root = logging.getLogger()
        assert root.level == logging.ERROR


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"


class TestResetLogging:
    def test_removes_handlers(self):
        setup_logging()
        reset_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 0
