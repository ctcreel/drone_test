"""Tests for the Storage CDK stack."""

import aws_cdk as cdk
import aws_cdk.assertions as assertions
from aws_cdk import aws_logs as logs

from infra.stacks.storage_stack import StorageStack


def _create_storage_stack() -> assertions.Template:
    """Create a storage stack and return the template."""
    app = cdk.App()
    config = {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "enable_backups": False,
    }
    stack = StorageStack(app, "TestStorage", environment="test", config=config)
    return assertions.Template.from_stack(stack)


class TestDynamoDBTable:
    """Tests for DynamoDB table creation."""

    def test_table_created(self) -> None:
        """DynamoDB table is created."""
        template = _create_storage_stack()
        template.resource_count_is("AWS::DynamoDB::Table", 1)

    def test_table_has_partition_and_sort_key(self) -> None:
        """Table uses pk/sk key schema."""
        template = _create_storage_stack()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": [
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
            },
        )

    def test_table_is_pay_per_request(self) -> None:
        """Table uses on-demand billing."""
        template = _create_storage_stack()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )

    def test_table_has_two_gsis(self) -> None:
        """Table has two global secondary indexes."""
        template = _create_storage_stack()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {"IndexName": "gsi1-status-created"}
                        ),
                        assertions.Match.object_like(
                            {"IndexName": "gsi2-drone-time"}
                        ),
                    ]
                ),
            },
        )

    def test_table_has_stream(self) -> None:
        """Table has DynamoDB streams enabled."""
        template = _create_storage_stack()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "StreamSpecification": {
                    "StreamViewType": "NEW_AND_OLD_IMAGES",
                },
            },
        )


class TestS3Bucket:
    """Tests for S3 bucket creation."""

    def test_bucket_created(self) -> None:
        """S3 bucket is created."""
        template = _create_storage_stack()
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_bucket_blocks_public_access(self) -> None:
        """Bucket blocks all public access."""
        template = _create_storage_stack()
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_bucket_has_lifecycle_rules(self) -> None:
        """Bucket has lifecycle rules configured."""
        template = _create_storage_stack()
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "LifecycleConfiguration": {
                    "Rules": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {"Id": "delete-non-match-captures"}
                            ),
                        ]
                    ),
                },
            },
        )


class TestStackOutputs:
    """Tests for stack CloudFormation outputs."""

    def test_table_name_output(self) -> None:
        """Table name is exported."""
        template = _create_storage_stack()
        template.has_output(
            "TableNameOutput",
            {"Export": {"Name": "DroneFleet-test-TableName"}},
        )

    def test_bucket_name_output(self) -> None:
        """Bucket name is exported."""
        template = _create_storage_stack()
        template.has_output(
            "BucketNameOutput",
            {"Export": {"Name": "DroneFleet-test-BucketName"}},
        )
