"""IoT stack: AWS IoT Core thing type, policies, and rules."""

from typing import Any

from aws_cdk import (
    CfnOutput,
    Stack,
)
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_iot as iot
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class IoTStack(Stack):
    """IoT Core resources for drone fleet communication."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        config: dict[str, Any],
        *,
        table: dynamodb.ITable,
        bucket_arn: str,
        image_queue: sqs.IQueue,
        telemetry_processor: lambda_.Function,
        **kwargs: Any,
    ) -> None:
        """Initialize the IoT stack.

        Args:
            scope: CDK scope.
            construct_id: Unique identifier for this stack.
            environment: Deployment environment.
            config: Environment-specific configuration.
            table: DynamoDB table for status writes.
            bucket_arn: S3 bucket ARN for image storage.
            image_queue: SQS queue for image analysis.
            telemetry_processor: Lambda function for telemetry processing.
            **kwargs: Additional stack properties.
        """
        super().__init__(scope, construct_id, **kwargs)

        self._environment = environment
        self._config = config

        # IoT Thing Type for fleet drones
        iot.CfnThingType(
            self,
            "DroneThingType",
            thing_type_name=f"drone-fleet-{environment}-drone",
            thing_type_properties=iot.CfnThingType.ThingTypePropertiesProperty(
                thing_type_description=f"Drone fleet drone - {environment}",
                searchable_attributes=["drone_id", "fleet_id", "status"],
            ),
        )

        # IoT Policy template for drone devices
        self.drone_policy = iot.CfnPolicy(
            self,
            "DroneMqttPolicy",
            policy_name=f"drone-fleet-{environment}-drone-policy",
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["iot:Connect"],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"client/${{iot:Connection.Thing.ThingName}}"
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["iot:Publish"],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topic/drone-fleet/${{iot:Connection.Thing.ThingName}}/telemetry/*",
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topic/drone-fleet/${{iot:Connection.Thing.ThingName}}/image/*",
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topic/drone-fleet/${{iot:Connection.Thing.ThingName}}/status/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["iot:Subscribe"],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topicfilter/drone-fleet/"
                            f"${{iot:Connection.Thing.ThingName}}/command/*",
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topicfilter/drone-fleet/fleet/broadcast/*",
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topicfilter/drone-fleet/fleet/coordination/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["iot:Receive"],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topic/drone-fleet/${{iot:Connection.Thing.ThingName}}/command/*",
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topic/drone-fleet/fleet/broadcast/*",
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"topic/drone-fleet/fleet/coordination/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:UpdateThingShadow",
                            "iot:GetThingShadow",
                        ],
                        "Resource": [
                            f"arn:aws:iot:{self.region}:{self.account}:"
                            f"thing/${{iot:Connection.Thing.ThingName}}"
                        ],
                    },
                ],
            },
        )

        # IAM role for IoT rules to invoke Lambda, write to DynamoDB, publish to SQS
        iot_rule_role = iam.Role(
            self,
            "IoTRuleRole",
            role_name=f"drone-fleet-{environment}-iot-rule-role",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),  # type: ignore[arg-type]
        )

        table.grant_write_data(iot_rule_role)
        image_queue.grant_send_messages(iot_rule_role)
        telemetry_processor.grant_invoke(iot_rule_role)

        # IoT Rule: telemetry → Lambda
        iot.CfnTopicRule(
            self,
            "TelemetryToLambdaRule",
            rule_name=f"drone_fleet_{environment}_telemetry_to_lambda",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT * FROM 'drone-fleet/+/telemetry/#'",
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        lambda_=iot.CfnTopicRule.LambdaActionProperty(
                            function_arn=telemetry_processor.function_arn,
                        ),
                    ),
                ],
                rule_disabled=False,
                aws_iot_sql_version="2016-03-23",
            ),
        )

        # IoT Rule: image captured → SQS
        iot.CfnTopicRule(
            self,
            "ImageToSqsRule",
            rule_name=f"drone_fleet_{environment}_image_to_sqs",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT * FROM 'drone-fleet/+/image/captured'",
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        sqs=iot.CfnTopicRule.SqsActionProperty(
                            queue_url=image_queue.queue_url,
                            role_arn=iot_rule_role.role_arn,
                        ),
                    ),
                ],
                rule_disabled=False,
                aws_iot_sql_version="2016-03-23",
            ),
        )

        # IoT Rule: status → DynamoDB
        iot.CfnTopicRule(
            self,
            "StatusToDynamoRule",
            rule_name=f"drone_fleet_{environment}_status_to_dynamo",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT * FROM 'drone-fleet/+/status/#'",
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        dynamo_d_bv2=iot.CfnTopicRule.DynamoDBv2ActionProperty(
                            put_item=iot.CfnTopicRule.PutItemInputProperty(
                                table_name=table.table_name,
                            ),
                            role_arn=iot_rule_role.role_arn,
                        ),
                    ),
                ],
                rule_disabled=False,
                aws_iot_sql_version="2016-03-23",
            ),
        )

        # Grant Lambda invoke from IoT
        telemetry_processor.add_permission(
            "AllowIoTInvoke",
            principal=iam.ServicePrincipal("iot.amazonaws.com"),  # type: ignore[arg-type]
            source_arn=f"arn:aws:iot:{self.region}:{self.account}:rule/"
            f"drone_fleet_{environment}_telemetry_to_lambda",
        )

        # Outputs
        CfnOutput(
            self,
            "IoTPolicyNameOutput",
            value=self.drone_policy.policy_name or "",
            description=f"IoT drone policy name for {environment}",
            export_name=f"DroneFleet-{environment}-IoTPolicyName",
        )
