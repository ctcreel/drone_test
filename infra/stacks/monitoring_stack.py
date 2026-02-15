"""Monitoring stack: CloudWatch dashboards, alarms, SNS notifications."""

from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class MonitoringStack(Stack):
    """CloudWatch alarms, dashboard, and SNS notifications."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        config: dict[str, Any],
        *,
        mission_planner: lambda_.Function,
        mission_controller: lambda_.Function,
        image_analyzer: lambda_.Function,
        telemetry_processor: lambda_.Function,
        fleet_coordinator: lambda_.Function,
        image_queue: sqs.IQueue,
        **kwargs: Any,
    ) -> None:
        """Initialize the monitoring stack.

        Args:
            scope: CDK scope.
            construct_id: Unique identifier for this stack.
            environment: Deployment environment.
            config: Environment-specific configuration.
            mission_planner: Mission planner Lambda function.
            mission_controller: Mission controller Lambda function.
            image_analyzer: Image analyzer Lambda function.
            telemetry_processor: Telemetry processor Lambda function.
            fleet_coordinator: Fleet coordinator Lambda function.
            image_queue: SQS queue for image analysis.
            **kwargs: Additional stack properties.
        """
        super().__init__(scope, construct_id, **kwargs)

        self._environment = environment
        self._config = config

        if not config["enable_monitoring"]:
            return

        # SNS topic for alarm notifications
        alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"drone-fleet-{environment}-alarms",
            display_name=f"Drone Fleet {environment} Alarms",
        )

        # Lambda error alarms for each function
        lambda_functions = {
            "MissionPlanner": mission_planner,
            "MissionController": mission_controller,
            "ImageAnalyzer": image_analyzer,
            "TelemetryProcessor": telemetry_processor,
            "FleetCoordinator": fleet_coordinator,
        }

        for name, function in lambda_functions.items():
            alarm = cloudwatch.Alarm(
                self,
                f"{name}ErrorAlarm",
                metric=function.metric_errors(period=Duration.minutes(5)),
                threshold=5,
                evaluation_periods=1,
                alarm_description=f"{name} errors for {environment}",
                alarm_name=f"drone-fleet-{environment}-{name}-errors",
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            alarm.add_alarm_action(
                cw_actions.SnsAction(alarm_topic)  # type: ignore[arg-type]
            )

        # Mission planner latency alarm (> 30 seconds)
        planner_latency_alarm = cloudwatch.Alarm(
            self,
            "MissionPlannerLatencyAlarm",
            metric=mission_planner.metric_duration(period=Duration.minutes(5)),
            threshold=30000,
            evaluation_periods=1,
            alarm_description=f"Mission planning latency > 30s for {environment}",
            alarm_name=f"drone-fleet-{environment}-planner-latency",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        planner_latency_alarm.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)  # type: ignore[arg-type]
        )

        # Image analyzer latency alarm (> 10 seconds)
        image_latency_alarm = cloudwatch.Alarm(
            self,
            "ImageAnalyzerLatencyAlarm",
            metric=image_analyzer.metric_duration(period=Duration.minutes(5)),
            threshold=10000,
            evaluation_periods=1,
            alarm_description=f"Image analysis latency > 10s for {environment}",
            alarm_name=f"drone-fleet-{environment}-image-latency",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        image_latency_alarm.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)  # type: ignore[arg-type]
        )

        # SQS queue depth alarm (> 50 messages)
        queue_depth_alarm = cloudwatch.Alarm(
            self,
            "ImageQueueDepthAlarm",
            metric=image_queue.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(1),
            ),
            threshold=50,
            evaluation_periods=3,
            alarm_description=f"Image analysis queue depth > 50 for {environment}",
            alarm_name=f"drone-fleet-{environment}-image-queue-depth",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        queue_depth_alarm.add_alarm_action(
            cw_actions.SnsAction(alarm_topic)  # type: ignore[arg-type]
        )

        # CloudWatch Dashboard
        dashboard = cloudwatch.Dashboard(
            self,
            "DroneFleetDashboard",
            dashboard_name=f"drone-fleet-{environment}",
        )

        # Lambda invocations and errors
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Invocations",
                left=[
                    function.metric_invocations(period=Duration.minutes(1))
                    for function in lambda_functions.values()
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Errors",
                left=[
                    function.metric_errors(period=Duration.minutes(1))
                    for function in lambda_functions.values()
                ],
                width=12,
            ),
        )

        # Lambda duration
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Duration (ms)",
                left=[
                    function.metric_duration(period=Duration.minutes(1))
                    for function in lambda_functions.values()
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Image Analysis Queue",
                left=[
                    image_queue.metric_approximate_number_of_messages_visible(
                        period=Duration.minutes(1),
                    ),
                    image_queue.metric_approximate_number_of_messages_not_visible(
                        period=Duration.minutes(1),
                    ),
                ],
                width=12,
            ),
        )

        # Outputs
        CfnOutput(
            self,
            "AlarmTopicArnOutput",
            value=alarm_topic.topic_arn,
            description=f"Alarm SNS topic ARN for {environment}",
            export_name=f"DroneFleet-{environment}-AlarmTopicArn",
        )

        CfnOutput(
            self,
            "DashboardNameOutput",
            value=dashboard.dashboard_name,
            description=f"CloudWatch dashboard for {environment}",
            export_name=f"DroneFleet-{environment}-DashboardName",
        )
