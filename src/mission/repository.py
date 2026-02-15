"""Mission data access layer."""

from datetime import UTC, datetime

from src.constants import PARTITION_KEY_MISSION
from src.exceptions.client_errors import ConflictError
from src.mission.models import Mission, MissionPlan, MissionStatus, validate_transition
from src.utils.dynamodb import DynamoDBClient


class MissionRepository:
    """Repository for mission CRUD operations."""

    def __init__(self, dynamodb_client: DynamoDBClient) -> None:
        """Initialize the mission repository.

        Args:
            dynamodb_client: DynamoDB client instance.
        """
        self._db = dynamodb_client

    def create(self, mission: Mission) -> Mission:
        """Create a new mission.

        Args:
            mission: Mission to create.

        Returns:
            Created mission.
        """
        self._db.put_item(mission.to_dynamodb_item())
        return mission

    def get(self, mission_id: str) -> Mission:
        """Get a mission by ID.

        Args:
            mission_id: Mission identifier.

        Returns:
            Mission entity.

        Raises:
            NotFoundError: If mission does not exist.
        """
        item = self._db.get_item(
            pk=f"{PARTITION_KEY_MISSION}{mission_id}",
            sk="METADATA",
        )
        return Mission.from_dynamodb_item(item)

    def update_status(
        self,
        mission_id: str,
        new_status: MissionStatus,
    ) -> Mission:
        """Update mission status with transition validation.

        Args:
            mission_id: Mission identifier.
            new_status: Target status.

        Returns:
            Updated mission.

        Raises:
            NotFoundError: If mission does not exist.
            ConflictError: If transition is invalid.
        """
        mission = self.get(mission_id)

        if not validate_transition(mission.status, new_status):
            raise ConflictError(
                message=f"Cannot transition from {mission.status} to {new_status}",
            )

        now = datetime.now(UTC).isoformat()
        self._db.update_item(
            pk=f"{PARTITION_KEY_MISSION}{mission_id}",
            sk="METADATA",
            updates={
                "status": new_status,
                "updated_at": now,
                "gsi1pk": new_status,
            },
        )

        mission.status = new_status
        mission.updated_at = now
        return mission

    def update_plan(
        self,
        mission_id: str,
        plan: MissionPlan,
    ) -> Mission:
        """Update mission with a generated plan.

        Args:
            mission_id: Mission identifier.
            plan: Generated mission plan.

        Returns:
            Updated mission.
        """
        now = datetime.now(UTC).isoformat()
        self._db.update_item(
            pk=f"{PARTITION_KEY_MISSION}{mission_id}",
            sk="METADATA",
            updates={
                "plan": plan.model_dump(),
                "status": MissionStatus.PLANNED,
                "updated_at": now,
                "gsi1pk": MissionStatus.PLANNED,
            },
        )

        return self.get(mission_id)

    def list_by_status(
        self,
        status: MissionStatus,
        *,
        limit: int = 50,
    ) -> list[Mission]:
        """List missions by status.

        Args:
            status: Mission status to filter by.
            limit: Maximum number of missions to return.

        Returns:
            List of matching missions.
        """
        items = self._db.query(
            pk=status,
            index_name="gsi1-status-created",
            limit=limit,
            scan_forward=False,
        )
        return [Mission.from_dynamodb_item(item) for item in items]

    def list_all(self, *, limit: int = 50) -> list[Mission]:
        """List recent missions across all statuses.

        Args:
            limit: Maximum number of missions to return.

        Returns:
            List of missions.
        """
        missions: list[Mission] = []
        for status in MissionStatus:
            items = self._db.query(
                pk=status,
                index_name="gsi1-status-created",
                limit=limit,
                scan_forward=False,
            )
            missions.extend(Mission.from_dynamodb_item(item) for item in items)

        missions.sort(key=lambda m: m.created_at, reverse=True)
        return missions[:limit]
