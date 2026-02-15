"""Processing stack: SQS, image analyzer Lambda, fleet coordinator."""

from pathlib import Path
from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

_LAMBDA_EXCLUDES = [
    "infra",
    "tests",
    "edge",
    "edge_tests",
    "infra_tests",
    "integration_tests",
    "simulation",
    "scripts",
    ".github",
    ".git",
    ".venv",
    "__pycache__",
    "*.md",
    "*.toml",
    "*.cfg",
    "docs",
    "cdk.out",
    ".pre-commit-config.yaml",
    ".editorconfig",
    ".gitignore",
    ".gitleaks.toml",
    "sonar-project.properties",
]


class ProcessingStack(Stack):
    """SQS queue, image analyzer, telemetry processor, fleet coordinator."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        config: dict[str, Any],
        *,
        table: dynamodb.ITable,
        bucket: s3.IBucket,
        **kwargs: Any,
    ) -> None:
        """Initialize the processing stack.

        Args:
            scope: CDK scope.
            construct_id: Unique identifier for this stack.
            environment: Deployment environment.
            config: Environment-specific configuration.
            table: DynamoDB table for data access.
            bucket: S3 bucket for image storage.
            **kwargs: Additional stack properties.
        """
        super().__init__(scope, construct_id, **kwargs)

        self._environment = environment
        self._config = config

        # Dead letter queue for failed image analysis
        image_dlq = sqs.Queue(
            self,
            "ImageAnalysisDLQ",
            queue_name=f"drone-fleet-{environment}-image-analysis-dlq",
            retention_period=Duration.days(14),
        )

        # SQS queue for image analysis
        self.image_queue = sqs.Queue(
            self,
            "ImageAnalysisQueue",
            queue_name=f"drone-fleet-{environment}-image-analysis",
            visibility_timeout=Duration.seconds(120),
            retention_period=Duration.days(7),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=image_dlq,
            ),
        )

        # Shared Lambda environment variables
        lambda_environment = {
            "TABLE_NAME": table.table_name,
            "BUCKET_NAME": bucket.bucket_name,
            "ENVIRONMENT": environment,
            "IMAGE_QUEUE_URL": self.image_queue.queue_url,
            "BEDROCK_MODEL_ID": config.get(
                "bedrock_model_id",
                "anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
        }

        # Image analyzer Lambda
        image_analyzer_log_group = logs.LogGroup(
            self,
            "ImageAnalyzerLogGroup",
            log_group_name=f"/aws/lambda/drone-fleet-{environment}-image-analyzer",
            retention=config["log_retention"],
            removal_policy=config["removal_policy"],
        )
        self.image_analyzer = lambda_.Function(
            self,
            "ImageAnalyzer",
            function_name=f"drone-fleet-{environment}-image-analyzer",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.handlers.image_analyzer.handler",
            code=lambda_.Code.from_asset(_PROJECT_ROOT, exclude=_LAMBDA_EXCLUDES),
            timeout=Duration.seconds(90),
            memory_size=1024,
            environment=lambda_environment,
            log_group=image_analyzer_log_group,
        )

        # Wire SQS → Lambda
        self.image_analyzer.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.image_queue,
                batch_size=1,
            )
        )

        # Grant permissions
        table.grant_read_write_data(self.image_analyzer)
        bucket.grant_read_write(self.image_analyzer)
        self.image_queue.grant_consume_messages(self.image_analyzer)

        # Grant Bedrock access
        self.image_analyzer.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )

        # Telemetry processor Lambda (invoked by IoT Rule)
        telemetry_processor_log_group = logs.LogGroup(
            self,
            "TelemetryProcessorLogGroup",
            log_group_name=f"/aws/lambda/drone-fleet-{environment}-telemetry-processor",
            retention=config["log_retention"],
            removal_policy=config["removal_policy"],
        )
        self.telemetry_processor = lambda_.Function(
            self,
            "TelemetryProcessor",
            function_name=f"drone-fleet-{environment}-telemetry-processor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.handlers.telemetry_processor.handler",
            code=lambda_.Code.from_asset(_PROJECT_ROOT, exclude=_LAMBDA_EXCLUDES),
            timeout=Duration.seconds(10),
            memory_size=256,
            environment=lambda_environment,
            log_group=telemetry_processor_log_group,
        )

        table.grant_read_write_data(self.telemetry_processor)

        # Grant IoT shadow access for telemetry processor
        self.telemetry_processor.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iot:UpdateThingShadow",
                    "iot:GetThingShadow",
                ],
                resources=[
                    f"arn:aws:iot:{self.region}:{self.account}:thing/*",
                ],
            )
        )

        # Fleet coordinator Lambda (scheduled)
        fleet_coordinator_log_group = logs.LogGroup(
            self,
            "FleetCoordinatorLogGroup",
            log_group_name=f"/aws/lambda/drone-fleet-{environment}-fleet-coordinator",
            retention=config["log_retention"],
            removal_policy=config["removal_policy"],
        )
        self.fleet_coordinator = lambda_.Function(
            self,
            "FleetCoordinator",
            function_name=f"drone-fleet-{environment}-fleet-coordinator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.handlers.fleet_coordinator.handler",
            code=lambda_.Code.from_asset(_PROJECT_ROOT, exclude=_LAMBDA_EXCLUDES),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment=lambda_environment,
            log_group=fleet_coordinator_log_group,
        )

        table.grant_read_write_data(self.fleet_coordinator)

        # Grant IoT publish for fleet coordination
        self.fleet_coordinator.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iot:Publish", "iot:DescribeEndpoint"],
                resources=["*"],
            )
        )

        # EventBridge rule: run fleet coordinator every 30 seconds
        events.Rule(
            self,
            "FleetCoordinatorSchedule",
            rule_name=f"drone-fleet-{environment}-fleet-coordinator-schedule",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[targets.LambdaFunction(self.fleet_coordinator)],  # type: ignore[list-item]
            enabled=config["enable_monitoring"],
        )

        # Outputs
        CfnOutput(
            self,
            "ImageQueueUrlOutput",
            value=self.image_queue.queue_url,
            description=f"Image analysis queue URL for {environment}",
            export_name=f"DroneFleet-{environment}-ImageQueueUrl",
        )

        CfnOutput(
            self,
            "ImageQueueArnOutput",
            value=self.image_queue.queue_arn,
            description=f"Image analysis queue ARN for {environment}",
            export_name=f"DroneFleet-{environment}-ImageQueueArn",
        )

        CfnOutput(
            self,
            "TelemetryProcessorArnOutput",
            value=self.telemetry_processor.function_arn,
            description=f"Telemetry processor ARN for {environment}",
            export_name=f"DroneFleet-{environment}-TelemetryProcessorArn",
        )
