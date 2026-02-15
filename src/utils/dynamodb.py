"""DynamoDB data access utilities."""

from decimal import Decimal
from typing import Any, cast

import boto3
from boto3.dynamodb.conditions import Key

from src.exceptions.client_errors import NotFoundError


def _convert_decimals(obj: Any) -> Any:
    """Convert Decimal values to int or float for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj == int(obj):
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        dict_obj = cast("dict[str, Any]", obj)
        return {k: _convert_decimals(v) for k, v in dict_obj.items()}
    if isinstance(obj, list):
        list_obj = cast("list[Any]", obj)
        return [_convert_decimals(item) for item in list_obj]
    return obj


def _sanitize_for_dynamodb(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB storage."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        dict_obj = cast("dict[str, Any]", obj)
        return {k: _sanitize_for_dynamodb(v) for k, v in dict_obj.items()}
    if isinstance(obj, list):
        list_obj = cast("list[Any]", obj)
        return [_sanitize_for_dynamodb(item) for item in list_obj]
    return obj


class DynamoDBClient:
    """Wrapper around DynamoDB table operations."""

    def __init__(self, table_name: str) -> None:
        """Initialize the DynamoDB client.

        Args:
            table_name: DynamoDB table name.
        """
        dynamodb = boto3.resource("dynamodb")  # type: ignore[call-overload]
        self._table = dynamodb.Table(table_name)

    def put_item(self, item: dict[str, Any]) -> None:
        """Write an item to the table.

        Args:
            item: Item to write.
        """
        self._table.put_item(Item=_sanitize_for_dynamodb(item))

    def get_item(self, pk: str, sk: str) -> dict[str, Any]:
        """Get a single item by primary key.

        Args:
            pk: Partition key value.
            sk: Sort key value.

        Returns:
            Item data.

        Raises:
            NotFoundError: If item does not exist.
        """
        response = self._table.get_item(Key={"pk": pk, "sk": sk})
        item = response.get("Item")
        if not item:
            raise NotFoundError(
                f"Item not found: {pk}/{sk}",
                resource_type="item",
                resource_id=f"{pk}/{sk}",
            )
        return _convert_decimals(item)

    def query(
        self,
        pk: str,
        sk_prefix: str | None = None,
        *,
        index_name: str | None = None,
        limit: int | None = None,
        scan_forward: bool = True,
    ) -> list[dict[str, Any]]:
        """Query items by partition key and optional sort key prefix.

        Args:
            pk: Partition key value.
            sk_prefix: Optional sort key prefix for begins_with.
            index_name: Optional GSI name to query.
            limit: Maximum number of items to return.
            scan_forward: Sort ascending if True, descending if False.

        Returns:
            List of matching items.
        """
        key_condition = Key("pk").eq(pk)
        if sk_prefix:
            key_condition = key_condition & Key("sk").begins_with(sk_prefix)

        if index_name:
            key_condition = Key("gsi1pk" if "gsi1" in index_name else "gsi2pk").eq(pk)
            if sk_prefix:
                sk_key = "gsi1sk" if "gsi1" in index_name else "gsi2sk"
                key_condition = key_condition & Key(sk_key).begins_with(sk_prefix)

        kwargs: dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_forward,
        }

        if index_name:
            kwargs["IndexName"] = index_name
        if limit:
            kwargs["Limit"] = limit

        response = self._table.query(**kwargs)
        items: list[dict[str, Any]] = response.get("Items", [])
        return [_convert_decimals(item) for item in items]

    def update_item(
        self,
        pk: str,
        sk: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update specific attributes of an item.

        Args:
            pk: Partition key value.
            sk: Sort key value.
            updates: Dictionary of attribute names to new values.

        Returns:
            Updated item attributes.
        """
        sanitized: dict[str, Any] = _sanitize_for_dynamodb(updates)
        update_parts: list[str] = []
        expression_values: dict[str, Any] = {}
        expression_names: dict[str, str] = {}

        for idx, (key, value) in enumerate(sanitized.items()):
            placeholder_val = f":v{idx}"
            placeholder_name = f"#n{idx}"
            update_parts.append(f"{placeholder_name} = {placeholder_val}")
            expression_values[placeholder_val] = value
            expression_names[placeholder_name] = key

        update_expression = "SET " + ", ".join(update_parts)

        response = self._table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues="ALL_NEW",
        )
        return _convert_decimals(response.get("Attributes", {}))

    def delete_item(self, pk: str, sk: str) -> None:
        """Delete an item by primary key.

        Args:
            pk: Partition key value.
            sk: Sort key value.
        """
        self._table.delete_item(Key={"pk": pk, "sk": sk})
