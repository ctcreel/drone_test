#!/usr/bin/env python3
"""CDK application entry point for drone fleet search infrastructure."""

import os
from datetime import UTC, datetime

import aws_cdk as cdk
from aws_cdk import aws_logs as logs

from stacks.api_stack import ApiStack
from stacks.iot_stack import IoTStack
from stacks.monitoring_stack import MonitoringStack
from stacks.processing_stack import ProcessingStack
from stacks.storage_stack import StorageStack

app = cdk.App()

# Get environment from context or environment variable
environment = (
    app.node.try_get_context("environment") or os.environ.get("CDK_ENVIRONMENT") or "development"
)

# Get account and region from context or environment
account = (
    app.node.try_get_context("account")
    or os.environ.get("CDK_DEFAULT_ACCOUNT")
    or os.environ.get("AWS_ACCOUNT_ID")
)

region = (
    app.node.try_get_context("region")
    or os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or "us-east-1"
)

# Environment-specific configuration
environment_config = {
    "development": {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention": logs.RetentionDays.ONE_WEEK,
        "enable_monitoring": False,
        "enable_backups": False,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_drones": 3,
    },
    "testing": {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention": logs.RetentionDays.TWO_WEEKS,
        "enable_monitoring": True,
        "enable_backups": False,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_drones": 5,
    },
    "demo": {
        "removal_policy": cdk.RemovalPolicy.SNAPSHOT,
        "log_retention": logs.RetentionDays.ONE_MONTH,
        "enable_monitoring": True,
        "enable_backups": True,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_drones": 5,
    },
    "production": {
        "removal_policy": cdk.RemovalPolicy.RETAIN,
        "log_retention": logs.RetentionDays.THREE_MONTHS,
        "enable_monitoring": True,
        "enable_backups": True,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_drones": 20,
    },
}

config = environment_config[environment]
cdk_env = cdk.Environment(account=account, region=region)

# Stack 1: Storage (DynamoDB + S3)
storage_stack = StorageStack(
    app,
    f"DroneFleet-{environment}-Storage",
    environment=environment,
    config=config,
    env=cdk_env,
)

# Stack 2: Processing (SQS + Lambdas - created before IoT because IoT needs references)
processing_stack = ProcessingStack(
    app,
    f"DroneFleet-{environment}-Processing",
    environment=environment,
    config=config,
    table=storage_stack.table,
    bucket=storage_stack.bucket,
    env=cdk_env,
)

# Stack 3: API (API Gateway + Cognito + Lambda handlers)
api_stack = ApiStack(
    app,
    f"DroneFleet-{environment}-Api",
    environment=environment,
    config=config,
    table=storage_stack.table,
    bucket=storage_stack.bucket,
    env=cdk_env,
)

# Stack 4: IoT Core (Thing types, policies, rules)
iot_stack = IoTStack(
    app,
    f"DroneFleet-{environment}-IoT",
    environment=environment,
    config=config,
    table=storage_stack.table,
    bucket_arn=storage_stack.bucket.bucket_arn,
    image_queue=processing_stack.image_queue,
    telemetry_processor=processing_stack.telemetry_processor,
    env=cdk_env,
)

# Stack 5: Monitoring (CloudWatch + SNS)
monitoring_stack = MonitoringStack(
    app,
    f"DroneFleet-{environment}-Monitoring",
    environment=environment,
    config=config,
    mission_planner=api_stack.mission_planner,
    mission_controller=api_stack.mission_controller,
    image_analyzer=processing_stack.image_analyzer,
    telemetry_processor=processing_stack.telemetry_processor,
    fleet_coordinator=processing_stack.fleet_coordinator,
    image_queue=processing_stack.image_queue,
    env=cdk_env,
)

# Apply tags to all resources
cdk.Tags.of(app).add("Project", "DroneFleetSearch")
cdk.Tags.of(app).add("ManagedBy", "CDK")
cdk.Tags.of(app).add("Environment", environment)
cdk.Tags.of(app).add("CostCenter", f"DroneFleet-{environment}")
cdk.Tags.of(app).add("DeployedAt", datetime.now(UTC).isoformat())

app.synth()
