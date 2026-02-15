"""Fleet data access layer."""

from datetime import UTC, datetime

from src.constants import PARTITION_KEY_DRONE
from src.exceptions.client_errors import ConflictError
from src.fleet.models import Drone, DroneStatus
from src.utils.dynamodb import DynamoDBClient


class DroneRepository:
    """Repository for drone CRUD operations."""

    def __init__(self, dynamodb_client: DynamoDBClient) -> None:
        """Initialize the drone repository.

        Args:
            dynamodb_client: DynamoDB client instance.
        """
        self._db = dynamodb_client

    def create(self, drone: Drone) -> Drone:
        """Create a new drone record.

        Args:
            drone: Drone to create.

        Returns:
            Created drone.
        """
        self._db.put_item(drone.to_dynamodb_item())
        return drone

    def get(self, drone_id: str) -> Drone:
        """Get a drone by ID.

        Args:
            drone_id: Drone identifier.

        Returns:
            Drone entity.

        Raises:
            NotFoundError: If drone does not exist.
        """
        item = self._db.get_item(
            pk=f"{PARTITION_KEY_DRONE}{drone_id}",
            sk="METADATA",
        )
        return Drone.from_dynamodb_item(item)

    def update_status(
        self,
        drone_id: str,
        new_status: DroneStatus,
    ) -> Drone:
        """Update drone status.

        Args:
            drone_id: Drone identifier.
            new_status: Target status.

        Returns:
            Updated drone.
        """
        now = datetime.now(UTC).isoformat()
        self._db.update_item(
            pk=f"{PARTITION_KEY_DRONE}{drone_id}",
            sk="METADATA",
            updates={
                "status": new_status,
                "updated_at": now,
                "gsi1pk": new_status,
            },
        )
        return self.get(drone_id)

    def update_last_seen(self, drone_id: str) -> None:
        """Update drone last_seen timestamp.

        Args:
            drone_id: Drone identifier.
        """
        now = datetime.now(UTC).isoformat()
        self._db.update_item(
            pk=f"{PARTITION_KEY_DRONE}{drone_id}",
            sk="METADATA",
            updates={"last_seen": now, "updated_at": now},
        )

    def update_health(
        self,
        drone_id: str,
        health_data: dict[str, float | int | str],
    ) -> None:
        """Update drone health metrics.

        Args:
            drone_id: Drone identifier.
            health_data: Health metrics dictionary.
        """
        now = datetime.now(UTC).isoformat()
        self._db.update_item(
            pk=f"{PARTITION_KEY_DRONE}{drone_id}",
            sk="METADATA",
            updates={"health": health_data, "updated_at": now},
        )

    def list_by_status(
        self,
        status: DroneStatus,
        *,
        limit: int = 50,
    ) -> list[Drone]:
        """List drones by status.

        Args:
            status: Drone status to filter by.
            limit: Maximum number of drones to return.

        Returns:
            List of matching drones.
        """
        items = self._db.query(
            pk=status,
            index_name="gsi1-status-created",
            limit=limit,
            scan_forward=False,
        )
        return [Drone.from_dynamodb_item(item) for item in items]

    def list_all(self, *, limit: int = 50) -> list[Drone]:
        """List all registered drones.

        Args:
            limit: Maximum number of drones to return.

        Returns:
            List of drones.
        """
        active_statuses = [
            DroneStatus.REGISTERED,
            DroneStatus.AVAILABLE,
            DroneStatus.ASSIGNED,
            DroneStatus.ACTIVE,
            DroneStatus.RETURNING,
            DroneStatus.MAINTENANCE,
        ]
        drones: list[Drone] = []
        for status in active_statuses:
            items = self._db.query(
                pk=status,
                index_name="gsi1-status-created",
                limit=limit,
                scan_forward=False,
            )
            drones.extend(Drone.from_dynamodb_item(item) for item in items)

        drones.sort(key=lambda d: d.created_at, reverse=True)
        return drones[:limit]

    def deregister(self, drone_id: str) -> Drone:
        """Mark a drone as deregistered.

        Args:
            drone_id: Drone identifier.

        Returns:
            Updated drone.

        Raises:
            ConflictError: If drone is currently active.
        """
        drone = self.get(drone_id)
        if drone.status == DroneStatus.ACTIVE:
            raise ConflictError(
                message="Cannot deregister an active drone",
            )
        return self.update_status(drone_id, DroneStatus.DEREGISTERED)
