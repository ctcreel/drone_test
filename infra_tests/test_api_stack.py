"""Tests for the API CDK stack."""

import aws_cdk as cdk
import aws_cdk.assertions as assertions
from aws_cdk import aws_logs as logs

from infra.stacks.api_stack import ApiStack
from infra.stacks.storage_stack import StorageStack


def _create_api_stack() -> assertions.Template:
    """Create an API stack and return the template."""
    app = cdk.App()
    config = {
        "removal_policy": cdk.RemovalPolicy.DESTROY,
        "log_retention": logs.RetentionDays.ONE_WEEK,
        "enable_monitoring": False,
        "enable_backups": False,
        "bedrock_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "max_drones": 3,
    }
    storage = StorageStack(app, "TestStorage", environment="test", config=config)
    stack = ApiStack(
        app,
        "TestApi",
        environment="test",
        config=config,
        table=storage.table,
        bucket=storage.bucket,
    )
    return assertions.Template.from_stack(stack)


class TestCognitoUserPool:
    """Tests for Cognito User Pool creation."""

    def test_user_pool_created(self) -> None:
        """Cognito User Pool is created."""
        template = _create_api_stack()
        template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_user_pool_has_email_sign_in(self) -> None:
        """User Pool allows email sign-in."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "UsernameAttributes": ["email"],
            },
        )

    def test_user_pool_has_password_policy(self) -> None:
        """User Pool has strong password policy."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Policies": {
                    "PasswordPolicy": assertions.Match.object_like(
                        {"MinimumLength": 12}
                    ),
                },
            },
        )

    def test_user_pool_client_created(self) -> None:
        """Cognito User Pool Client is created."""
        template = _create_api_stack()
        template.resource_count_is("AWS::Cognito::UserPoolClient", 1)


class TestLambdaFunctions:
    """Tests for API Lambda functions."""

    def test_three_lambda_functions_created(self) -> None:
        """Three API Lambda functions are created."""
        template = _create_api_stack()
        template.resource_count_is("AWS::Lambda::Function", 3)

    def test_mission_controller_function(self) -> None:
        """Mission controller Lambda has correct configuration."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "drone-fleet-test-mission-controller",
                "Runtime": "python3.12",
                "Timeout": 30,
                "MemorySize": 512,
            },
        )

    def test_mission_planner_function(self) -> None:
        """Mission planner Lambda has longer timeout for Bedrock."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "drone-fleet-test-mission-planner",
                "Runtime": "python3.12",
                "Timeout": 60,
                "MemorySize": 1024,
            },
        )

    def test_drone_registrar_function(self) -> None:
        """Drone registrar Lambda has correct configuration."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "drone-fleet-test-drone-registrar",
                "Runtime": "python3.12",
                "Timeout": 30,
                "MemorySize": 256,
            },
        )


class TestApiGateway:
    """Tests for API Gateway creation."""

    def test_rest_api_created(self) -> None:
        """API Gateway REST API is created."""
        template = _create_api_stack()
        template.resource_count_is("AWS::ApiGateway::RestApi", 1)

    def test_api_has_correct_name(self) -> None:
        """API has the correct name."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::ApiGateway::RestApi",
            {"Name": "drone-fleet-test-api"},
        )

    def test_cognito_authorizer_created(self) -> None:
        """Cognito authorizer is created for the API."""
        template = _create_api_stack()
        template.resource_count_is("AWS::ApiGateway::Authorizer", 1)


class TestIamPermissions:
    """Tests for IAM permissions."""

    def test_bedrock_access_policy(self) -> None:
        """Mission planner has Bedrock access policy."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {
                                    "Action": [
                                        "bedrock:InvokeModel",
                                        "bedrock:InvokeModelWithResponseStream",
                                    ],
                                    "Effect": "Allow",
                                }
                            ),
                        ]
                    ),
                },
            },
        )

    def test_iot_access_policy(self) -> None:
        """Drone registrar has IoT access policy."""
        template = _create_api_stack()
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {
                                    "Action": assertions.Match.array_with(
                                        ["iot:CreateThing"]
                                    ),
                                    "Effect": "Allow",
                                }
                            ),
                        ]
                    ),
                },
            },
        )


class TestStackOutputs:
    """Tests for stack CloudFormation outputs."""

    def test_api_endpoint_output(self) -> None:
        """API endpoint is exported."""
        template = _create_api_stack()
        template.has_output(
            "ApiEndpointOutput",
            {"Export": {"Name": "DroneFleet-test-ApiEndpoint"}},
        )

    def test_user_pool_id_output(self) -> None:
        """User Pool ID is exported."""
        template = _create_api_stack()
        template.has_output(
            "UserPoolIdOutput",
            {"Export": {"Name": "DroneFleet-test-UserPoolId"}},
        )
