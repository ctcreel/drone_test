"""Analysis data access layer for detection management."""

from datetime import UTC, datetime

from src.analysis.models import Detection, ReviewDecision
from src.constants import PARTITION_KEY_MISSION
from src.utils.dynamodb import DynamoDBClient
from src.utils.s3 import S3Client


class DetectionRepository:
    """Repository for detection CRUD operations."""

    def __init__(
        self,
        dynamodb_client: DynamoDBClient,
        s3_client: S3Client,
    ) -> None:
        """Initialize the detection repository.

        Args:
            dynamodb_client: DynamoDB client instance.
            s3_client: S3 client instance.
        """
        self._db = dynamodb_client
        self._s3 = s3_client

    def create(self, detection: Detection) -> Detection:
        """Create a new detection record.

        Args:
            detection: Detection to create.

        Returns:
            Created detection.
        """
        self._db.put_item(detection.to_dynamodb_item())
        return detection

    def get(self, mission_id: str, detection_id: str) -> Detection:
        """Get a detection by mission and detection ID.

        Args:
            mission_id: Mission identifier.
            detection_id: Detection identifier.

        Returns:
            Detection entity.

        Raises:
            NotFoundError: If detection does not exist.
        """
        item = self._db.get_item(
            pk=f"{PARTITION_KEY_MISSION}{mission_id}",
            sk=f"DETECTION#{detection_id}",
        )
        return Detection.from_dynamodb_item(item)

    def list_for_mission(
        self,
        mission_id: str,
        *,
        limit: int = 100,
    ) -> list[Detection]:
        """List all detections for a mission.

        Args:
            mission_id: Mission identifier.
            limit: Maximum number of detections to return.

        Returns:
            List of detections.
        """
        items = self._db.query(
            pk=f"{PARTITION_KEY_MISSION}{mission_id}",
            sk_prefix="DETECTION#",
            limit=limit,
        )
        return [Detection.from_dynamodb_item(item) for item in items]

    def review(
        self,
        mission_id: str,
        detection_id: str,
        review: ReviewDecision,
    ) -> Detection:
        """Apply a review decision to a detection.

        Args:
            mission_id: Mission identifier.
            detection_id: Detection identifier.
            review: Review decision with operator info.

        Returns:
            Updated detection.
        """
        now = datetime.now(UTC).isoformat()
        self._db.update_item(
            pk=f"{PARTITION_KEY_MISSION}{mission_id}",
            sk=f"DETECTION#{detection_id}",
            updates={
                "reviewed": review.decision,
                "reviewed_by": review.operator_id,
                "reviewed_at": now,
            },
        )
        return self.get(mission_id, detection_id)
