"""Tests for the Monitoring CDK stack."""

import aws_cdk as cdk
import aws_cdk.assertions as assertions
from aws_cdk import aws_logs as logs

from infra.stacks.api_stack import ApiStack
from infra.stacks.monitoring_stack import MonitoringStack
from infra.stacks.processing_stack import ProcessingStack
from infra.stacks.storage_stack import StorageStack


def _create_monitoring_stack(
    *,
    enable_monitoring: bool = True,
) -> assertions.Template:
    """Create a monitoring stack and return the template."""
    app = cdk.App()
    config = {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention": logs.RetentionDays.ONE_WEEK,
        "enable_monitoring": enable_monitoring,
        "enable_backups": False,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_drones": 3,
    }
    storage = StorageStack(app, "TestStorage", environment="test", config=config)
    processing = ProcessingStack(
        app,
        "TestProcessing",
        environment="test",
        config=config,
        table=storage.table,
        bucket=storage.bucket,
    )
    api = ApiStack(
        app,
        "TestApi",
        environment="test",
        config=config,
        table=storage.table,
        bucket=storage.bucket,
    )
    stack = MonitoringStack(
        app,
        "TestMonitoring",
        environment="test",
        config=config,
        mission_planner=api.mission_planner,
        mission_controller=api.mission_controller,
        image_analyzer=processing.image_analyzer,
        telemetry_processor=processing.telemetry_processor,
        fleet_coordinator=processing.fleet_coordinator,
        image_queue=processing.image_queue,
    )
    return assertions.Template.from_stack(stack)


class TestMonitoringEnabled:
    """Tests when monitoring is enabled."""

    def test_alarm_topic_created(self) -> None:
        """SNS alarm topic is created."""
        template = _create_monitoring_stack(enable_monitoring=True)
        template.resource_count_is("AWS::SNS::Topic", 1)

    def test_alarm_topic_has_correct_name(self) -> None:
        """Alarm topic has the correct name."""
        template = _create_monitoring_stack(enable_monitoring=True)
        template.has_resource_properties(
            "AWS::SNS::Topic",
            {"TopicName": "drone-fleet-test-alarms"},
        )

    def test_lambda_error_alarms_created(self) -> None:
        """Lambda error alarms are created for all functions."""
        template = _create_monitoring_stack(enable_monitoring=True)
        template.resource_count_is("AWS::CloudWatch::Alarm", 8)

    def test_dashboard_created(self) -> None:
        """CloudWatch dashboard is created."""
        template = _create_monitoring_stack(enable_monitoring=True)
        template.resource_count_is("AWS::CloudWatch::Dashboard", 1)


class TestMonitoringDisabled:
    """Tests when monitoring is disabled."""

    def test_no_resources_created(self) -> None:
        """No monitoring resources are created when disabled."""
        template = _create_monitoring_stack(enable_monitoring=False)
        template.resource_count_is("AWS::SNS::Topic", 0)
        template.resource_count_is("AWS::CloudWatch::Alarm", 0)
        template.resource_count_is("AWS::CloudWatch::Dashboard", 0)


class TestStackOutputs:
    """Tests for stack CloudFormation outputs."""

    def test_alarm_topic_arn_output(self) -> None:
        """Alarm topic ARN is exported when monitoring enabled."""
        template = _create_monitoring_stack(enable_monitoring=True)
        template.has_output(
            "AlarmTopicArnOutput",
            {"Export": {"Name": "DroneFleet-test-AlarmTopicArn"}},
        )

    def test_dashboard_name_output(self) -> None:
        """Dashboard name is exported when monitoring enabled."""
        template = _create_monitoring_stack(enable_monitoring=True)
        template.has_output(
            "DashboardNameOutput",
            {"Export": {"Name": "DroneFleet-test-DashboardName"}},
        )
