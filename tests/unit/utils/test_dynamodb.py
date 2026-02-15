"""Tests for DynamoDB client utilities."""

import boto3
import pytest
from moto import mock_aws

from src.exceptions.client_errors import NotFoundError
from src.utils.dynamodb import DynamoDBClient


@pytest.fixture()
def dynamodb_table():
    """Create a mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
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
        table.wait_until_exists()
        yield table


class TestDynamoDBClientPutAndGet:
    """Tests for put_item and get_item."""

    def test_put_and_get_item(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({
            "pk": "TEST#1",
            "sk": "METADATA",
            "name": "test item",
            "count": 42,
        })
        item = client.get_item("TEST#1", "METADATA")
        assert item["name"] == "test item"
        assert item["count"] == 42

    def test_get_nonexistent_item_raises(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        with pytest.raises(NotFoundError):
            client.get_item("MISSING#1", "METADATA")

    def test_float_to_decimal_conversion(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({
            "pk": "TEST#float",
            "sk": "METADATA",
            "latitude": 40.7128,
            "nested": {"longitude": -74.006},
        })
        item = client.get_item("TEST#float", "METADATA")
        assert isinstance(item["latitude"], float)
        assert item["latitude"] == pytest.approx(40.7128)
        assert item["nested"]["longitude"] == pytest.approx(-74.006)


class TestDynamoDBClientQuery:
    """Tests for query operations."""

    def test_query_by_partition_key(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        for i in range(3):
            client.put_item({
                "pk": "BATCH#1",
                "sk": f"ITEM#{i}",
                "index": i,
            })
        items = client.query("BATCH#1")
        assert len(items) == 3

    def test_query_with_sk_prefix(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({"pk": "PFX#1", "sk": "A#1", "val": "a"})
        client.put_item({"pk": "PFX#1", "sk": "B#1", "val": "b"})
        items = client.query("PFX#1", "A#")
        assert len(items) == 1
        assert items[0]["val"] == "a"

    def test_query_with_limit(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        for i in range(5):
            client.put_item({
                "pk": "LIM#1",
                "sk": f"ITEM#{i:03d}",
                "index": i,
            })
        items = client.query("LIM#1", limit=2)
        assert len(items) == 2

    def test_query_gsi(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({
            "pk": "MISSION#1",
            "sk": "METADATA",
            "gsi1pk": "planned",
            "gsi1sk": "2024-01-01T00:00:00Z",
        })
        client.put_item({
            "pk": "MISSION#2",
            "sk": "METADATA",
            "gsi1pk": "planned",
            "gsi1sk": "2024-01-02T00:00:00Z",
        })
        items = client.query("planned", index_name="gsi1-status-created")
        assert len(items) == 2

    def test_query_scan_forward_false(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({
            "pk": "MISSION#1",
            "sk": "METADATA",
            "gsi1pk": "active",
            "gsi1sk": "2024-01-01",
        })
        client.put_item({
            "pk": "MISSION#2",
            "sk": "METADATA",
            "gsi1pk": "active",
            "gsi1sk": "2024-01-02",
        })
        items = client.query(
            "active",
            index_name="gsi1-status-created",
            scan_forward=False,
        )
        assert items[0]["gsi1sk"] == "2024-01-02"


class TestDynamoDBClientUpdate:
    """Tests for update_item."""

    def test_update_attributes(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({
            "pk": "UPD#1",
            "sk": "METADATA",
            "status": "created",
            "count": 0,
        })
        result = client.update_item(
            "UPD#1", "METADATA", {"status": "planned", "count": 1},
        )
        assert result["status"] == "planned"
        assert result["count"] == 1

    def test_update_reflects_in_get(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({"pk": "UPD#2", "sk": "METADATA", "val": "old"})
        client.update_item("UPD#2", "METADATA", {"val": "new"})
        item = client.get_item("UPD#2", "METADATA")
        assert item["val"] == "new"


class TestDynamoDBClientDelete:
    """Tests for delete_item."""

    def test_delete_item(self, dynamodb_table) -> None:
        client = DynamoDBClient("test-table")
        client.put_item({"pk": "DEL#1", "sk": "METADATA", "val": "x"})
        client.delete_item("DEL#1", "METADATA")
        with pytest.raises(NotFoundError):
            client.get_item("DEL#1", "METADATA")
