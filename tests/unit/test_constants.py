"""Tests for application constants."""

from src.constants import (
    CONNECTIVITY_DEGRADED_THRESHOLD,
    DEFAULT_LAMBDA_TIMEOUT,
    IMAGE_CAPTURE_INTERVAL_SECONDS,
    MAX_FLEET_SIZE,
    MAX_WAYPOINTS_PER_SEGMENT,
    MINIMUM_CLEARANCE_METERS,
    MQTT_COMMAND_TOPIC,
    MQTT_TELEMETRY_TOPIC,
    MQTT_TOPIC_PREFIX,
    OBSTACLE_AVOIDANCE_LOOP_FREQUENCY_HZ,
    OBSTACLE_DETECTION_RANGE_METERS,
    PARTITION_KEY_DRONE,
    PARTITION_KEY_MISSION,
    RETENTION_DAYS_CONFIRMED,
    RETENTION_DAYS_NON_MATCH,
    S3_PREFIX_IMAGES,
    SERVICE_NAME,
    SERVICE_VERSION,
)


class TestServiceConstants:
    def test_service_name(self):
        assert SERVICE_NAME == "drone-fleet-search"

    def test_service_version(self):
        assert SERVICE_VERSION == "0.1.0"


class TestMqttConstants:
    def test_topic_prefix(self):
        assert MQTT_TOPIC_PREFIX == "drone-fleet"

    def test_command_topic(self):
        assert MQTT_COMMAND_TOPIC == "command"

    def test_telemetry_topic(self):
        assert MQTT_TELEMETRY_TOPIC == "telemetry"


class TestDynamoDbConstants:
    def test_mission_prefix(self):
        assert PARTITION_KEY_MISSION == "MISSION#"

    def test_drone_prefix(self):
        assert PARTITION_KEY_DRONE == "DRONE#"


class TestS3Constants:
    def test_images_prefix(self):
        assert S3_PREFIX_IMAGES == "images/"


class TestTimeoutConstants:
    def test_lambda_timeout(self):
        assert DEFAULT_LAMBDA_TIMEOUT == 30

    def test_degraded_threshold(self):
        assert CONNECTIVITY_DEGRADED_THRESHOLD == 10


class TestFleetConstants:
    def test_max_fleet_size(self):
        assert MAX_FLEET_SIZE == 5

    def test_max_waypoints(self):
        assert MAX_WAYPOINTS_PER_SEGMENT == 100


class TestEdgeConstants:
    def test_obstacle_range(self):
        assert OBSTACLE_DETECTION_RANGE_METERS == 10.0

    def test_minimum_clearance(self):
        assert MINIMUM_CLEARANCE_METERS == 2.0

    def test_avoidance_frequency(self):
        assert OBSTACLE_AVOIDANCE_LOOP_FREQUENCY_HZ == 10

    def test_image_capture_interval(self):
        assert IMAGE_CAPTURE_INTERVAL_SECONDS == 5


class TestRetentionConstants:
    def test_non_match_retention(self):
        assert RETENTION_DAYS_NON_MATCH == 7

    def test_confirmed_retention(self):
        assert RETENTION_DAYS_CONFIRMED == 365
