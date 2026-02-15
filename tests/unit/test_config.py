"""Tests for application configuration."""

import pytest

from src.config import Environment, Settings, get_settings, validate_startup_config


class TestEnvironmentEnum:
    def test_development_value(self):
        assert Environment.DEVELOPMENT.value == "development"

    def test_testing_value(self):
        assert Environment.TESTING.value == "testing"

    def test_demo_value(self):
        assert Environment.DEMO.value == "demo"

    def test_production_value(self):
        assert Environment.PRODUCTION.value == "production"


class TestSettingsDefaults:
    def test_default_service_name(self):
        settings = Settings()
        assert settings.service_name == "drone-fleet-search"

    def test_default_environment(self):
        settings = Settings()
        assert settings.environment == Environment.DEVELOPMENT

    def test_default_aws_region(self):
        settings = Settings()
        assert settings.aws_region == "us-east-1"

    def test_default_table_name(self):
        settings = Settings()
        assert settings.table_name == "drone-fleet-development"

    def test_default_image_bucket_name(self):
        settings = Settings()
        assert settings.image_bucket_name == "drone-fleet-images-development"

    def test_default_log_level(self):
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_default_max_fleet_size(self):
        settings = Settings()
        assert settings.max_fleet_size == 5

    def test_default_api_timeout(self):
        settings = Settings()
        assert settings.api_timeout_seconds == 30

    def test_default_bedrock_model_id(self):
        settings = Settings()
        assert "anthropic" in settings.bedrock_model_id

    def test_default_enable_tracing(self):
        settings = Settings()
        assert settings.enable_tracing is False

    def test_default_enable_metrics(self):
        settings = Settings()
        assert settings.enable_metrics is False

    def test_default_mission_planning_timeout(self):
        settings = Settings()
        assert settings.mission_planning_timeout_seconds == 60


class TestSettingsFromEnvironment:
    def test_custom_service_name(self, monkeypatch):
        monkeypatch.setenv("SERVICE_NAME", "custom-service")
        settings = Settings()
        assert settings.service_name == "custom-service"

    def test_custom_environment(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = Settings()
        assert settings.environment == Environment.PRODUCTION

    def test_custom_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        settings = Settings()
        assert settings.log_level == "DEBUG"

    def test_custom_max_fleet_size(self, monkeypatch):
        monkeypatch.setenv("MAX_FLEET_SIZE", "3")
        settings = Settings()
        assert settings.max_fleet_size == 3


class TestSettingsValidation:
    def test_invalid_log_level_raises(self):
        with pytest.raises(ValueError, match="log_level must be one of"):
            Settings(log_level="INVALID")

    def test_log_level_case_insensitive(self):
        settings = Settings(log_level="warning")
        assert settings.log_level == "WARNING"

    def test_api_timeout_minimum(self):
        with pytest.raises(ValueError):
            Settings(api_timeout_seconds=0)

    def test_api_timeout_maximum(self):
        with pytest.raises(ValueError):
            Settings(api_timeout_seconds=301)

    def test_max_fleet_size_minimum(self):
        with pytest.raises(ValueError):
            Settings(max_fleet_size=0)


class TestSettingsProperties:
    def test_is_production_true(self):
        settings = Settings(environment=Environment.PRODUCTION)
        assert settings.is_production is True

    def test_is_production_false(self):
        settings = Settings(environment=Environment.DEVELOPMENT)
        assert settings.is_production is False

    def test_is_development_true(self):
        settings = Settings()
        assert settings.is_development is True

    def test_is_development_false(self):
        settings = Settings(environment=Environment.PRODUCTION)
        assert settings.is_development is False


class TestGetSettings:
    def test_returns_settings_instance(self):
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_cached_returns_same_instance(self):
        get_settings.cache_clear()
        first = get_settings()
        second = get_settings()
        assert first is second


class TestValidateStartupConfig:
    def test_returns_settings(self):
        get_settings.cache_clear()
        settings = validate_startup_config()
        assert isinstance(settings, Settings)
