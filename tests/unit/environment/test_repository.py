"""Tests for environment repository."""

import boto3
import pytest
from moto import mock_aws

from src.environment.models import (
    BuildingFootprint,
    EnvironmentModel,
    NoFlyZone,
    ObstacleZone,
)
from src.environment.repository import EnvironmentRepository
from src.exceptions.client_errors import NotFoundError
from src.utils.dynamodb import DynamoDBClient
from src.utils.s3 import S3Client


def _make_environment(environment_id: str = "env-001") -> EnvironmentModel:
    return EnvironmentModel(
        environment_id=environment_id,
        name="Test Area",
        bounds=[[40.0, -74.0], [40.1, -73.9]],
        building_footprints=[
            BuildingFootprint(
                coordinates=[[0.0, 0.0], [1.0, 0.0]],
                height=30.0,
            ),
        ],
        obstacle_zones=[
            ObstacleZone(coordinates=[[0.0, 0.0]], description="Crane"),
        ],
        no_fly_zones=[
            NoFlyZone(coordinates=[[0.0, 0.0]], description="School"),
        ],
    )


@pytest.fixture()
def environment_repo():
    """Create an environment repository with mock AWS."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        db_client = DynamoDBClient("test-table")
        s3_client = S3Client("test-bucket")
        yield EnvironmentRepository(db_client, s3_client)


class TestEnvironmentRepositoryCreate:
    """Tests for creating environments."""

    def test_create_environment(
        self, environment_repo: EnvironmentRepository,
    ) -> None:
        env = _make_environment()
        created = environment_repo.create(env)
        assert created.environment_id == "env-001"
        assert created.created_at != ""

    def test_create_preserves_existing_created_at(
        self, environment_repo: EnvironmentRepository,
    ) -> None:
        env = _make_environment()
        env.created_at = "2024-01-01T00:00:00Z"
        created = environment_repo.create(env)
        assert created.created_at == "2024-01-01T00:00:00Z"


class TestEnvironmentRepositoryGet:
    """Tests for retrieving environments."""

    def test_get_environment(
        self, environment_repo: EnvironmentRepository,
    ) -> None:
        environment_repo.create(_make_environment())
        retrieved = environment_repo.get("env-001")
        assert retrieved.environment_id == "env-001"
        assert retrieved.name == "Test Area"
        assert len(retrieved.building_footprints) == 1
        assert len(retrieved.obstacle_zones) == 1
        assert len(retrieved.no_fly_zones) == 1

    def test_get_nonexistent_raises(
        self, environment_repo: EnvironmentRepository,
    ) -> None:
        with pytest.raises(NotFoundError):
            environment_repo.get("nonexistent")


class TestEnvironmentRepositoryGetMetadata:
    """Tests for retrieving environment metadata."""

    def test_get_metadata(
        self, environment_repo: EnvironmentRepository,
    ) -> None:
        environment_repo.create(_make_environment())
        metadata = environment_repo.get_metadata("env-001")
        assert metadata["environment_id"] == "env-001"
        assert metadata["building_count"] == 1
