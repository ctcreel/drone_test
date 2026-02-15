"""Tests for the Processing CDK stack."""

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_logs as logs
from infra.stacks.processing_stack import ProcessingStack
from infra.stacks.storage_stack import StorageStack


def _create_processing_stack() -> assertions.Template:
    """Create a processing stack and return the template."""
    app = cdk.App()
    config = {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention": logs.RetentionDays.ONE_WEEK,
        "enable_monitoring": False,
        "enable_backups": False,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    storage = StorageStack(app, "TestStorage", environment="test", config=config)
    stack = ProcessingStack(
        app,
        "TestProcessing",
        environment="test",
        config=config,
        table=storage.table,
        bucket=storage.bucket,
    )
    return assertions.Template.from_stack(stack)


class TestSqsQueue:
    """Tests for SQS queue creation."""

    def test_image_queue_created(self) -> None:
        """Image analysis queue is created."""
        template = _create_processing_stack()
        template.resource_count_is("AWS::SQS::Queue", 2)

    def test_image_queue_has_dlq(self) -> None:
        """Image queue has a dead letter queue."""
        template = _create_processing_stack()
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "QueueName": "drone-fleet-test-image-analysis",
                "RedrivePolicy": assertions.Match.object_like(
                    {"maxReceiveCount": 3}
                ),
            },
        )


class TestLambdaFunctions:
    """Tests for Lambda function creation."""

    def test_three_lambda_functions_created(self) -> None:
        """Three processing Lambda functions are created."""
        template = _create_processing_stack()
        template.resource_count_is("AWS::Lambda::Function", 3)

    def test_image_analyzer_has_correct_config(self) -> None:
        """Image analyzer has correct timeout and memory."""
        template = _create_processing_stack()
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "drone-fleet-test-image-analyzer",
                "Runtime": "python3.12",
                "Timeout": 90,
                "MemorySize": 1024,
            },
        )

    def test_telemetry_processor_has_correct_config(self) -> None:
        """Telemetry processor has correct timeout and memory."""
        template = _create_processing_stack()
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "drone-fleet-test-telemetry-processor",
                "Runtime": "python3.12",
                "Timeout": 10,
                "MemorySize": 256,
            },
        )

    def test_fleet_coordinator_has_correct_config(self) -> None:
        """Fleet coordinator has correct timeout and memory."""
        template = _create_processing_stack()
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "drone-fleet-test-fleet-coordinator",
                "Runtime": "python3.12",
                "Timeout": 30,
                "MemorySize": 512,
            },
        )


class TestEventBridgeSchedule:
    """Tests for EventBridge schedule."""

    def test_fleet_coordinator_schedule_exists(self) -> None:
        """Fleet coordinator has an EventBridge schedule."""
        template = _create_processing_stack()
        template.has_resource_properties(
            "AWS::Events::Rule",
            {
                "ScheduleExpression": "rate(1 minute)",
            },
        )


class TestSqsEventSource:
    """Tests for SQS event source mapping."""

    def test_image_analyzer_has_sqs_trigger(self) -> None:
        """Image analyzer is triggered by SQS queue."""
        template = _create_processing_stack()
        template.resource_count_is("AWS::Lambda::EventSourceMapping", 1)
