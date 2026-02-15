"""Tests for environment domain models."""

import pytest
from pydantic import ValidationError

from src.environment.models import (
    BuildingFootprint,
    EnvironmentModel,
    NoFlyZone,
    ObstacleZone,
)


class TestBuildingFootprint:
    """Tests for BuildingFootprint model."""

    def test_valid_footprint(self) -> None:
        footprint = BuildingFootprint(
            coordinates=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]],
            ground_elevation=10.0,
            height=30.0,
        )
        assert footprint.ground_elevation == 10.0
        assert footprint.height == 30.0

    def test_defaults(self) -> None:
        footprint = BuildingFootprint(coordinates=[])
        assert footprint.ground_elevation == 0.0
        assert footprint.height == 0.0


class TestObstacleZone:
    """Tests for ObstacleZone model."""

    def test_valid_obstacle(self) -> None:
        zone = ObstacleZone(
            coordinates=[[0.0, 0.0], [1.0, 0.0]],
            clearance_meters=15.0,
            description="Power line",
        )
        assert zone.clearance_meters == 15.0

    def test_defaults(self) -> None:
        zone = ObstacleZone(coordinates=[])
        assert zone.clearance_meters == 10.0
        assert zone.description == ""


class TestNoFlyZone:
    """Tests for NoFlyZone model."""

    def test_valid_no_fly(self) -> None:
        zone = NoFlyZone(
            coordinates=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]],
            description="Airport approach",
        )
        assert zone.description == "Airport approach"


class TestEnvironmentModel:
    """Tests for EnvironmentModel."""

    def test_minimal_environment(self) -> None:
        env = EnvironmentModel(
            environment_id="env-001",
            name="Test Area",
            bounds=[[0.0, 0.0], [1.0, 1.0]],
        )
        assert env.environment_id == "env-001"
        assert env.building_footprints == []
        assert env.obstacle_zones == []
        assert env.no_fly_zones == []

    def test_full_environment(self) -> None:
        env = EnvironmentModel(
            environment_id="env-002",
            name="Urban Area",
            bounds=[[40.0, -74.0], [40.1, -73.9]],
            building_footprints=[
                BuildingFootprint(
                    coordinates=[[0.0, 0.0]], height=50.0,
                ),
            ],
            obstacle_zones=[
                ObstacleZone(
                    coordinates=[[0.0, 0.0]], description="Crane",
                ),
            ],
            no_fly_zones=[
                NoFlyZone(
                    coordinates=[[0.0, 0.0]], description="School",
                ),
            ],
        )
        assert len(env.building_footprints) == 1
        assert len(env.obstacle_zones) == 1
        assert len(env.no_fly_zones) == 1

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EnvironmentModel(
                environment_id="env-003",
                name="",
                bounds=[],
            )

    def test_to_dynamodb_item(self) -> None:
        env = EnvironmentModel(
            environment_id="env-ddb",
            name="DDB Test",
            bounds=[[0.0, 0.0], [1.0, 1.0]],
            building_footprints=[BuildingFootprint(coordinates=[])],
            obstacle_zones=[ObstacleZone(coordinates=[])],
            no_fly_zones=[
                NoFlyZone(coordinates=[]),
                NoFlyZone(coordinates=[]),
            ],
            created_at="2024-01-01T00:00:00Z",
        )
        item = env.to_dynamodb_item()
        assert item["pk"] == "ENV#env-ddb"
        assert item["sk"] == "METADATA"
        assert item["building_count"] == 1
        assert item["obstacle_count"] == 1
        assert item["no_fly_count"] == 2
        assert item["name"] == "DDB Test"

    def test_from_dynamodb_item_metadata_only(self) -> None:
        item = {
            "pk": "ENV#env-meta",
            "sk": "METADATA",
            "environment_id": "env-meta",
            "name": "Meta Test",
            "bounds": [[0.0, 0.0]],
            "created_at": "2024-01-01T00:00:00Z",
        }
        env = EnvironmentModel.from_dynamodb_item(item)
        assert env.environment_id == "env-meta"
        assert env.name == "Meta Test"
        assert env.building_footprints == []

    def test_from_dynamodb_item_with_full_model(self) -> None:
        item = {
            "pk": "ENV#env-full",
            "sk": "METADATA",
            "environment_id": "env-full",
            "name": "Full Test",
            "bounds": [[0.0, 0.0]],
        }
        full_model = {
            "environment_id": "env-full",
            "name": "Full Test",
            "bounds": [[0.0, 0.0]],
            "building_footprints": [
                {"coordinates": [[0.0, 0.0]], "ground_elevation": 0, "height": 50},
            ],
        }
        env = EnvironmentModel.from_dynamodb_item(item, full_model)
        assert len(env.building_footprints) == 1
        assert env.building_footprints[0].height == 50
