"""Environment data access layer."""

from datetime import UTC, datetime
from typing import Any

from src.constants import PARTITION_KEY_ENVIRONMENT, S3_PREFIX_ENVIRONMENTS
from src.environment.models import EnvironmentModel
from src.utils.dynamodb import DynamoDBClient
from src.utils.s3 import S3Client


class EnvironmentRepository:
    """Repository for environment model CRUD operations."""

    def __init__(
        self,
        dynamodb_client: DynamoDBClient,
        s3_client: S3Client,
    ) -> None:
        """Initialize the environment repository.

        Args:
            dynamodb_client: DynamoDB client instance.
            s3_client: S3 client instance.
        """
        self._db = dynamodb_client
        self._s3 = s3_client

    def create(self, environment: EnvironmentModel) -> EnvironmentModel:
        """Create a new environment model.

        Args:
            environment: Environment model to create.

        Returns:
            Created environment.
        """
        if not environment.created_at:
            environment.created_at = datetime.now(UTC).isoformat()

        self._db.put_item(environment.to_dynamodb_item())

        s3_key = f"{S3_PREFIX_ENVIRONMENTS}{environment.environment_id}/model.json"
        self._s3.put_json(s3_key, environment.model_dump())

        return environment

    def get(self, environment_id: str) -> EnvironmentModel:
        """Get an environment model by ID.

        Args:
            environment_id: Environment identifier.

        Returns:
            EnvironmentModel entity.

        Raises:
            NotFoundError: If environment does not exist.
        """
        s3_key = f"{S3_PREFIX_ENVIRONMENTS}{environment_id}/model.json"
        full_model = self._s3.get_json(s3_key)
        return EnvironmentModel(**full_model)

    def get_metadata(self, environment_id: str) -> dict[str, Any]:
        """Get environment metadata from DynamoDB.

        Args:
            environment_id: Environment identifier.

        Returns:
            Environment metadata.
        """
        return self._db.get_item(
            pk=f"{PARTITION_KEY_ENVIRONMENT}{environment_id}",
            sk="METADATA",
        )
