"""Tests for fleet repository."""

import boto3
import pytest
from moto import mock_aws

from src.exceptions.client_errors import ConflictError, NotFoundError
from src.fleet.models import Drone, DroneStatus
from src.fleet.repository import DroneRepository
from src.utils.dynamodb import DynamoDBClient


@pytest.fixture()
def drone_repo():
    """Create a drone repository backed by mock DynamoDB."""
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
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi1-status-created",
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        db_client = DynamoDBClient("test-table")
        yield DroneRepository(db_client)


class TestDroneRepositoryCreate:
    """Tests for creating drones."""

    def test_create_and_get(self, drone_repo: DroneRepository) -> None:
        drone = Drone(
            drone_id="d-001",
            name="Alpha",
            iot_thing_name="drone-fleet-d-001",
        )
        created = drone_repo.create(drone)
        assert created.drone_id == "d-001"

        retrieved = drone_repo.get("d-001")
        assert retrieved.name == "Alpha"

    def test_get_nonexistent_raises(self, drone_repo: DroneRepository) -> None:
        with pytest.raises(NotFoundError):
            drone_repo.get("nonexistent")


class TestDroneRepositoryUpdate:
    """Tests for updating drones."""

    def test_update_status(self, drone_repo: DroneRepository) -> None:
        drone_repo.create(Drone(drone_id="d-status", name="Status Test"))
        updated = drone_repo.update_status("d-status", DroneStatus.AVAILABLE)
        assert updated.status == DroneStatus.AVAILABLE

    def test_update_last_seen(self, drone_repo: DroneRepository) -> None:
        drone_repo.create(Drone(drone_id="d-seen", name="Seen Test"))
        drone_repo.update_last_seen("d-seen")
        drone = drone_repo.get("d-seen")
        assert drone.last_seen != ""

    def test_update_health(self, drone_repo: DroneRepository) -> None:
        drone_repo.create(Drone(drone_id="d-health", name="Health Test"))
        drone_repo.update_health("d-health", {
            "battery_voltage": 11.5,
            "battery_remaining_percent": 65.0,
            "estimated_flight_time_seconds": 1500,
        })
        drone = drone_repo.get("d-health")
        assert drone.health is not None
        assert drone.health.battery_remaining_percent == 65.0


class TestDroneRepositoryList:
    """Tests for listing drones."""

    def test_list_by_status(self, drone_repo: DroneRepository) -> None:
        for i in range(3):
            drone_repo.create(Drone(
                drone_id=f"d-list-{i}",
                name=f"Drone {i}",
                status=DroneStatus.AVAILABLE,
            ))
        drones = drone_repo.list_by_status(DroneStatus.AVAILABLE)
        assert len(drones) == 3

    def test_list_all(self, drone_repo: DroneRepository) -> None:
        drone_repo.create(Drone(
            drone_id="d-all-1", name="One",
            status=DroneStatus.REGISTERED,
        ))
        drone_repo.create(Drone(
            drone_id="d-all-2", name="Two",
            status=DroneStatus.AVAILABLE,
        ))
        drones = drone_repo.list_all()
        assert len(drones) == 2

    def test_list_all_excludes_deregistered(
        self, drone_repo: DroneRepository,
    ) -> None:
        drone_repo.create(Drone(
            drone_id="d-dereg", name="Deregistered",
            status=DroneStatus.DEREGISTERED,
        ))
        drones = drone_repo.list_all()
        assert len(drones) == 0


class TestDroneRepositoryDeregister:
    """Tests for deregistering drones."""

    def test_deregister_available_drone(
        self, drone_repo: DroneRepository,
    ) -> None:
        drone_repo.create(Drone(
            drone_id="d-dereg",
            name="To Deregister",
            status=DroneStatus.AVAILABLE,
        ))
        updated = drone_repo.deregister("d-dereg")
        assert updated.status == DroneStatus.DEREGISTERED

    def test_deregister_active_drone_raises(
        self, drone_repo: DroneRepository,
    ) -> None:
        drone_repo.create(Drone(
            drone_id="d-active",
            name="Active Drone",
            status=DroneStatus.ACTIVE,
        ))
        with pytest.raises(ConflictError):
            drone_repo.deregister("d-active")
