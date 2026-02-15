"""Tests for the IoT CDK stack."""

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_logs as logs
from infra.stacks.iot_stack import IoTStack
from infra.stacks.processing_stack import ProcessingStack
from infra.stacks.storage_stack import StorageStack


def _create_iot_stack() -> assertions.Template:
    """Create an IoT stack and return the template."""
    app = cdk.App()
    config = {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention": logs.RetentionDays.ONE_WEEK,
        "enable_monitoring": False,
        "enable_backups": False,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
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
    stack = IoTStack(
        app,
        "TestIoT",
        environment="test",
        config=config,
        table=storage.table,
        bucket_arn=storage.bucket.bucket_arn,
        image_queue=processing.image_queue,
        telemetry_processor=processing.telemetry_processor,
    )
    return assertions.Template.from_stack(stack)


class TestIoTThingType:
    """Tests for IoT Thing Type."""

    def test_thing_type_created(self) -> None:
        """IoT Thing Type is created."""
        template = _create_iot_stack()
        template.resource_count_is("AWS::IoT::ThingType", 1)

    def test_thing_type_has_correct_name(self) -> None:
        """Thing Type has the correct name."""
        template = _create_iot_stack()
        template.has_resource_properties(
            "AWS::IoT::ThingType",
            {"ThingTypeName": "drone-fleet-test-drone"},
        )


class TestIoTPolicy:
    """Tests for IoT MQTT Policy."""

    def test_mqtt_policy_created(self) -> None:
        """IoT MQTT policy is created."""
        template = _create_iot_stack()
        template.resource_count_is("AWS::IoT::Policy", 1)

    def test_policy_has_correct_name(self) -> None:
        """Policy has the correct name."""
        template = _create_iot_stack()
        template.has_resource_properties(
            "AWS::IoT::Policy",
            {"PolicyName": "drone-fleet-test-drone-policy"},
        )


class TestIoTRules:
    """Tests for IoT Topic Rules."""

    def test_three_topic_rules_created(self) -> None:
        """Three IoT topic rules are created."""
        template = _create_iot_stack()
        template.resource_count_is("AWS::IoT::TopicRule", 3)

    def test_telemetry_rule_sql(self) -> None:
        """Telemetry rule has correct SQL filter."""
        template = _create_iot_stack()
        template.has_resource_properties(
            "AWS::IoT::TopicRule",
            {
                "RuleName": "drone_fleet_test_telemetry_to_lambda",
                "TopicRulePayload": assertions.Match.object_like(
                    {"Sql": "SELECT * FROM 'drone-fleet/+/telemetry/#'"}
                ),
            },
        )

    def test_image_rule_sql(self) -> None:
        """Image capture rule has correct SQL filter."""
        template = _create_iot_stack()
        template.has_resource_properties(
            "AWS::IoT::TopicRule",
            {
                "RuleName": "drone_fleet_test_image_to_sqs",
                "TopicRulePayload": assertions.Match.object_like(
                    {"Sql": "SELECT * FROM 'drone-fleet/+/image/captured'"}
                ),
            },
        )

    def test_status_rule_sql(self) -> None:
        """Status rule has correct SQL filter."""
        template = _create_iot_stack()
        template.has_resource_properties(
            "AWS::IoT::TopicRule",
            {
                "RuleName": "drone_fleet_test_status_to_dynamo",
                "TopicRulePayload": assertions.Match.object_like(
                    {"Sql": "SELECT * FROM 'drone-fleet/+/status/#'"}
                ),
            },
        )


class TestIoTRuleRole:
    """Tests for IoT Rule IAM Role."""

    def test_iot_rule_role_created(self) -> None:
        """IAM role for IoT rules is created."""
        template = _create_iot_stack()
        template.has_resource_properties(
            "AWS::IAM::Role",
            {"RoleName": "drone-fleet-test-iot-rule-role"},
        )


class TestStackOutputs:
    """Tests for stack CloudFormation outputs."""

    def test_policy_name_output(self) -> None:
        """IoT policy name is exported."""
        template = _create_iot_stack()
        template.has_output(
            "IoTPolicyNameOutput",
            {"Export": {"Name": "DroneFleet-test-IoTPolicyName"}},
        )
