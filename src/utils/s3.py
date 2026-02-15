"""S3 storage utilities."""

import json
from typing import Any

import boto3

from src.exceptions.client_errors import NotFoundError


class S3Client:
    """Wrapper around S3 operations."""

    def __init__(self, bucket_name: str) -> None:
        """Initialize the S3 client.

        Args:
            bucket_name: S3 bucket name.
        """
        self._s3 = boto3.client("s3")  # type: ignore[call-overload]
        self._bucket_name = bucket_name

    def put_json(self, key: str, data: dict[str, Any]) -> None:
        """Write JSON data to S3.

        Args:
            key: S3 object key.
            data: JSON-serializable data.
        """
        self._s3.put_object(
            Bucket=self._bucket_name,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
        )

    def get_json(self, key: str) -> dict[str, Any]:
        """Read JSON data from S3.

        Args:
            key: S3 object key.

        Returns:
            Parsed JSON data.

        Raises:
            NotFoundError: If object does not exist.
        """
        try:
            response = self._s3.get_object(
                Bucket=self._bucket_name,
                Key=key,
            )
        except self._s3.exceptions.NoSuchKey as error:
            raise NotFoundError(
                f"S3 object not found: {key}",
                resource_type="s3_object",
                resource_id=key,
            ) from error
        body: str = response["Body"].read().decode("utf-8")
        result: dict[str, Any] = json.loads(body)
        return result

    def delete_object(self, key: str) -> None:
        """Delete an object from S3.

        Args:
            key: S3 object key.
        """
        self._s3.delete_object(
            Bucket=self._bucket_name,
            Key=key,
        )
