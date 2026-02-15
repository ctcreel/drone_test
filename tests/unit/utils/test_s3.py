"""Tests for S3 client utilities."""

import boto3
import pytest
from moto import mock_aws

from src.exceptions.client_errors import NotFoundError
from src.utils.s3 import S3Client


@pytest.fixture()
def s3_bucket():
    """Create a mock S3 bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield


class TestS3ClientPutJson:
    """Tests for put_json."""

    def test_put_json(self, s3_bucket) -> None:
        client = S3Client("test-bucket")
        client.put_json("test/data.json", {"key": "value", "count": 42})
        result = client.get_json("test/data.json")
        assert result["key"] == "value"
        assert result["count"] == 42


class TestS3ClientGetJson:
    """Tests for get_json."""

    def test_get_json(self, s3_bucket) -> None:
        client = S3Client("test-bucket")
        client.put_json("path/obj.json", {"nested": {"a": 1}})
        result = client.get_json("path/obj.json")
        assert result["nested"]["a"] == 1

    def test_get_nonexistent_raises(self, s3_bucket) -> None:
        client = S3Client("test-bucket")
        with pytest.raises(NotFoundError):
            client.get_json("missing/file.json")


class TestS3ClientDelete:
    """Tests for delete_object."""

    def test_delete_object(self, s3_bucket) -> None:
        client = S3Client("test-bucket")
        client.put_json("del/obj.json", {"val": "x"})
        client.delete_object("del/obj.json")
        with pytest.raises(NotFoundError):
            client.get_json("del/obj.json")
