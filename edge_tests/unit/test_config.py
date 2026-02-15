"""Tests for edge tier configuration."""

import pytest
from pydantic import ValidationError

from edge.config import ConnectivityMode, EdgeSettings, get_edge_settings


class TestConnectivityMode:
    def test_aws_iot_value(self):
        assert ConnectivityMode.AWS_IOT.value == "aws_iot"

    def test_mosquitto_value(self):
        assert ConnectivityMode.MOSQUITTO.value == "mosquitto"

    def test_all_modes_count(self):
        assert len(ConnectivityMode) == 2

    def test_is_string_enum(self):
        assert isinstance(ConnectivityMode.AWS_IOT, str)
        assert ConnectivityMode.AWS_IOT == "aws_iot"


class TestEdgeSettingsDefaults:
    def test_default_mqtt_endpoint(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.mqtt_endpoint == "localhost"

    def test_default_mqtt_port(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.mqtt_port == 1883

    def test_default_connectivity_mode(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.connectivity_mode == ConnectivityMode.MOSQUITTO

    def test_default_mavlink_connection(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.mavlink_connection == "tcp:127.0.0.1:5760"

    def test_default_mavlink_baud_rate(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.mavlink_baud_rate == 57600

    def test_default_certificate_paths_empty(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.certificate_path == ""
        assert settings.private_key_path == ""
        assert settings.root_ca_path == ""

    def test_default_obstacle_detection_range(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.obstacle_detection_range_meters == 10.0

    def test_default_minimum_clearance(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.minimum_clearance_meters == 2.0

    def test_default_image_capture_interval(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.image_capture_interval_seconds == 5

    def test_default_image_compression_quality(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.image_compression_quality == 85

    def test_default_telemetry_report_interval(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.telemetry_report_interval_seconds == 2

    def test_default_degraded_threshold(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.degraded_threshold_seconds == 10

    def test_default_holding_threshold(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.holding_threshold_seconds == 30

    def test_default_return_threshold(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.return_threshold_seconds == 120

    def test_default_log_level(self):
        settings = EdgeSettings(drone_id="drone-test")
        assert settings.log_level == "INFO"


class TestEdgeSettingsFromEnvironment:
    def test_drone_id_from_env(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "alpha-007")
        settings = EdgeSettings()
        assert settings.drone_id == "alpha-007"

    def test_mqtt_endpoint_from_env(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test")
        monkeypatch.setenv("DRONE_MQTT_ENDPOINT", "iot.example.com")
        settings = EdgeSettings()
        assert settings.mqtt_endpoint == "iot.example.com"

    def test_mqtt_port_from_env(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test")
        monkeypatch.setenv("DRONE_MQTT_PORT", "8883")
        settings = EdgeSettings()
        assert settings.mqtt_port == 8883

    def test_connectivity_mode_from_env(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test")
        monkeypatch.setenv("DRONE_CONNECTIVITY_MODE", "aws_iot")
        settings = EdgeSettings()
        assert settings.connectivity_mode == ConnectivityMode.AWS_IOT

    def test_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test")
        monkeypatch.setenv("DRONE_LOG_LEVEL", "debug")
        settings = EdgeSettings()
        assert settings.log_level == "DEBUG"

    def test_obstacle_detection_range_from_env(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test")
        monkeypatch.setenv("DRONE_OBSTACLE_DETECTION_RANGE_METERS", "25.0")
        settings = EdgeSettings()
        assert settings.obstacle_detection_range_meters == 25.0

    def test_env_prefix_is_drone(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test-via-env")
        settings = EdgeSettings()
        assert settings.drone_id == "test-via-env"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "  test-drone  ")
        settings = EdgeSettings()
        assert settings.drone_id == "test-drone"

    def test_ignores_extra_env_vars(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test")
        monkeypatch.setenv("DRONE_UNKNOWN_SETTING", "value")
        # Should not raise
        settings = EdgeSettings()
        assert settings.drone_id == "test"


class TestEdgeSettingsValidation:
    def test_drone_id_required(self):
        with pytest.raises(ValidationError):
            EdgeSettings()

    def test_drone_id_empty_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="")

    def test_invalid_log_level_raises(self):
        with pytest.raises(ValueError, match="log_level must be one of"):
            EdgeSettings(drone_id="test", log_level="INVALID")

    def test_log_level_case_insensitive(self):
        settings = EdgeSettings(drone_id="test", log_level="warning")
        assert settings.log_level == "WARNING"

    def test_log_level_all_valid_values(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            settings = EdgeSettings(drone_id="test", log_level=level)
            assert settings.log_level == level

    def test_mqtt_port_minimum(self):
        settings = EdgeSettings(drone_id="test", mqtt_port=1)
        assert settings.mqtt_port == 1

    def test_mqtt_port_maximum(self):
        settings = EdgeSettings(drone_id="test", mqtt_port=65535)
        assert settings.mqtt_port == 65535

    def test_mqtt_port_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", mqtt_port=0)

    def test_mqtt_port_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", mqtt_port=65536)

    def test_obstacle_detection_range_minimum(self):
        settings = EdgeSettings(drone_id="test", obstacle_detection_range_meters=1.0)
        assert settings.obstacle_detection_range_meters == 1.0

    def test_obstacle_detection_range_maximum(self):
        settings = EdgeSettings(drone_id="test", obstacle_detection_range_meters=50.0)
        assert settings.obstacle_detection_range_meters == 50.0

    def test_obstacle_detection_range_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", obstacle_detection_range_meters=0.5)

    def test_obstacle_detection_range_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", obstacle_detection_range_meters=51.0)

    def test_minimum_clearance_minimum(self):
        settings = EdgeSettings(drone_id="test", minimum_clearance_meters=0.5)
        assert settings.minimum_clearance_meters == 0.5

    def test_minimum_clearance_maximum(self):
        settings = EdgeSettings(drone_id="test", minimum_clearance_meters=10.0)
        assert settings.minimum_clearance_meters == 10.0

    def test_minimum_clearance_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", minimum_clearance_meters=0.1)

    def test_minimum_clearance_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", minimum_clearance_meters=11.0)

    def test_image_compression_quality_minimum(self):
        settings = EdgeSettings(drone_id="test", image_compression_quality=1)
        assert settings.image_compression_quality == 1

    def test_image_compression_quality_maximum(self):
        settings = EdgeSettings(drone_id="test", image_compression_quality=100)
        assert settings.image_compression_quality == 100

    def test_image_compression_quality_zero_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", image_compression_quality=0)

    def test_image_compression_quality_above_max_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", image_compression_quality=101)

    def test_degraded_threshold_minimum(self):
        settings = EdgeSettings(drone_id="test", degraded_threshold_seconds=5)
        assert settings.degraded_threshold_seconds == 5

    def test_degraded_threshold_maximum(self):
        settings = EdgeSettings(drone_id="test", degraded_threshold_seconds=60)
        assert settings.degraded_threshold_seconds == 60

    def test_degraded_threshold_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSettings(drone_id="test", degraded_threshold_seconds=4)

    def test_holding_threshold_minimum(self):
        settings = EdgeSettings(drone_id="test", holding_threshold_seconds=15)
        assert settings.holding_threshold_seconds == 15

    def test_holding_threshold_maximum(self):
        settings = EdgeSettings(drone_id="test", holding_threshold_seconds=120)
        assert settings.holding_threshold_seconds == 120

    def test_return_threshold_minimum(self):
        settings = EdgeSettings(drone_id="test", return_threshold_seconds=60)
        assert settings.return_threshold_seconds == 60

    def test_return_threshold_maximum(self):
        settings = EdgeSettings(drone_id="test", return_threshold_seconds=600)
        assert settings.return_threshold_seconds == 600

    def test_telemetry_interval_minimum(self):
        settings = EdgeSettings(drone_id="test", telemetry_report_interval_seconds=1)
        assert settings.telemetry_report_interval_seconds == 1

    def test_telemetry_interval_maximum(self):
        settings = EdgeSettings(drone_id="test", telemetry_report_interval_seconds=30)
        assert settings.telemetry_report_interval_seconds == 30

    def test_image_capture_interval_minimum(self):
        settings = EdgeSettings(drone_id="test", image_capture_interval_seconds=1)
        assert settings.image_capture_interval_seconds == 1

    def test_image_capture_interval_maximum(self):
        settings = EdgeSettings(drone_id="test", image_capture_interval_seconds=60)
        assert settings.image_capture_interval_seconds == 60


class TestGetEdgeSettings:
    def test_returns_settings_instance(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test-cached")
        get_edge_settings.cache_clear()
        settings = get_edge_settings()
        assert isinstance(settings, EdgeSettings)
        assert settings.drone_id == "test-cached"

    def test_cached_returns_same_instance(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test-cached")
        get_edge_settings.cache_clear()
        first = get_edge_settings()
        second = get_edge_settings()
        assert first is second

    def test_cache_clear_creates_new_instance(self, monkeypatch):
        monkeypatch.setenv("DRONE_DRONE_ID", "test-v1")
        get_edge_settings.cache_clear()
        first = get_edge_settings()

        monkeypatch.setenv("DRONE_DRONE_ID", "test-v2")
        get_edge_settings.cache_clear()
        second = get_edge_settings()

        assert first is not second
        assert first.drone_id == "test-v1"
        assert second.drone_id == "test-v2"
