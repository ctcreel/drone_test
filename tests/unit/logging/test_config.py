"""Tests for logging configuration."""

from src.logging.config import LogFormat, LoggingConfig, LogLevel, get_logging_config


class TestLogLevel:
    def test_debug_value(self):
        assert LogLevel.DEBUG.value == "DEBUG"

    def test_info_value(self):
        assert LogLevel.INFO.value == "INFO"

    def test_warning_value(self):
        assert LogLevel.WARNING.value == "WARNING"


class TestLogFormat:
    def test_json_value(self):
        assert LogFormat.JSON.value == "json"

    def test_human_value(self):
        assert LogFormat.HUMAN.value == "human"


class TestLoggingConfig:
    def test_default_log_level(self):
        config = LoggingConfig()
        assert config.log_level == LogLevel.INFO

    def test_default_log_format(self):
        config = LoggingConfig()
        assert config.log_format == LogFormat.JSON

    def test_default_service_name(self):
        config = LoggingConfig()
        assert config.service_name == "drone-fleet-search"

    def test_custom_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        config = LoggingConfig()
        assert config.log_level == LogLevel.DEBUG


class TestGetLoggingConfig:
    def test_returns_config(self):
        get_logging_config.cache_clear()
        config = get_logging_config()
        assert isinstance(config, LoggingConfig)
