"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _clear_environment(monkeypatch):
    """Clear environment variables that affect settings."""
    env_vars_to_clear = [
        "SERVICE_NAME",
        "ENVIRONMENT",
        "AWS_REGION",
        "TABLE_NAME",
        "IMAGE_BUCKET_NAME",
        "IOT_ENDPOINT",
        "BEDROCK_MODEL_ID",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "ENABLE_TRACING",
        "ENABLE_METRICS",
        "API_TIMEOUT_SECONDS",
        "MAX_FLEET_SIZE",
        "MISSION_PLANNING_TIMEOUT_SECONDS",
    ]
    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)
