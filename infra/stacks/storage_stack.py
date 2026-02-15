"""Storage stack: DynamoDB single-table + S3 with lifecycle rules."""

from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from constructs import Construct


class StorageStack(Stack):
    """DynamoDB table and S3 bucket for the drone fleet search system."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        config: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Initialize the storage stack.

        Args:
            scope: CDK scope.
            construct_id: Unique identifier for this stack.
            environment: Deployment environment.
            config: Environment-specific configuration.
            **kwargs: Additional stack properties.
        """
        super().__init__(scope, construct_id, **kwargs)

        self._environment = environment
        self._config = config

        # DynamoDB single-table design
        self.table = dynamodb.Table(
            self,
            "DroneFleetTable",
            table_name=f"drone-fleet-{environment}",
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="sk",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=config["removal_policy"],
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=config["enable_backups"],
            ),
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # GSI-1: status + created_at (active missions, pending detections)
        self.table.add_global_secondary_index(
            index_name="gsi1-status-created",
            partition_key=dynamodb.Attribute(
                name="gsi1pk",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="gsi1sk",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI-2: drone_id + timestamp (telemetry history, mission participation)
        self.table.add_global_secondary_index(
            index_name="gsi2-drone-time",
            partition_key=dynamodb.Attribute(
                name="gsi2pk",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="gsi2sk",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # S3 bucket for images, environments, mission plans
        self.bucket = s3.Bucket(
            self,
            "DroneFleetBucket",
            bucket_name=f"drone-fleet-{environment}-{self.account}",
            removal_policy=config["removal_policy"],
            auto_delete_objects=config["removal_policy"] == RemovalPolicy.DESTROY,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=config["enable_backups"],
            enforce_ssl=True,
        )

        # Lifecycle rule: delete non-match captures after 7 days
        self.bucket.add_lifecycle_rule(
            id="delete-non-match-captures",
            prefix="images/captures/",
            expiration=Duration.days(7),
            enabled=True,
        )

        # Lifecycle rule: delete dismissed detections after 30 days
        self.bucket.add_lifecycle_rule(
            id="delete-dismissed-detections",
            tag_filters={"reviewed": "dismissed"},
            expiration=Duration.days(30),
            enabled=True,
        )

        # Lifecycle rule: unreviewed detections to IA at 30d, delete at 90d
        self.bucket.add_lifecycle_rule(
            id="expire-unreviewed-detections",
            tag_filters={"reviewed": "pending"},
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(30),
                ),
            ],
            expiration=Duration.days(90),
            enabled=True,
        )

        # Lifecycle rule: confirmed detections to IA at 90d, Glacier at 1 year
        self.bucket.add_lifecycle_rule(
            id="archive-confirmed-detections",
            tag_filters={"reviewed": "confirmed"},
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(90),
                ),
                s3.Transition(
                    storage_class=s3.StorageClass.GLACIER,
                    transition_after=Duration.days(365),
                ),
            ],
            enabled=True,
        )

        # Lifecycle rule: archive mission plans after 90 days
        self.bucket.add_lifecycle_rule(
            id="archive-mission-plans",
            prefix="mission-plans/",
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(90),
                ),
                s3.Transition(
                    storage_class=s3.StorageClass.GLACIER,
                    transition_after=Duration.days(365),
                ),
            ],
            enabled=True,
        )

        # Outputs
        CfnOutput(
            self,
            "TableNameOutput",
            value=self.table.table_name,
            description=f"DynamoDB table name for {environment}",
            export_name=f"DroneFleet-{environment}-TableName",
        )

        CfnOutput(
            self,
            "TableArnOutput",
            value=self.table.table_arn,
            description=f"DynamoDB table ARN for {environment}",
            export_name=f"DroneFleet-{environment}-TableArn",
        )

        CfnOutput(
            self,
            "BucketNameOutput",
            value=self.bucket.bucket_name,
            description=f"S3 bucket name for {environment}",
            export_name=f"DroneFleet-{environment}-BucketName",
        )

        CfnOutput(
            self,
            "BucketArnOutput",
            value=self.bucket.bucket_arn,
            description=f"S3 bucket ARN for {environment}",
            export_name=f"DroneFleet-{environment}-BucketArn",
        )
