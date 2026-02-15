"""API stack: API Gateway, Lambda functions, Cognito."""

from pathlib import Path
from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
_LAYERS_DIR = str(Path(_PROJECT_ROOT) / "layers" / "dependencies")

_LAMBDA_EXCLUDES = [
    "infra",
    "tests",
    "edge",
    "edge_tests",
    "infra_tests",
    "integration_tests",
    "simulation",
    "scripts",
    "layers",
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


class ApiStack(Stack):
    """API Gateway with Lambda handlers and Cognito auth."""

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
        """Initialize the API stack.

        Args:
            scope: CDK scope.
            construct_id: Unique identifier for this stack.
            environment: Deployment environment.
            config: Environment-specific configuration.
            table: DynamoDB table for data access.
            bucket: S3 bucket for image/environment storage.
            **kwargs: Additional stack properties.
        """
        super().__init__(scope, construct_id, **kwargs)

        self._environment = environment
        self._config = config

        user_pool, user_pool_client = self._create_cognito(environment, config)
        lambda_environment = self._build_lambda_environment(
            table, bucket, environment, user_pool, config
        )
        self._create_lambda_functions(environment, config, lambda_environment)
        self._grant_permissions(table, bucket)
        self._create_api_gateway(environment, config, user_pool)
        self._create_outputs(environment, user_pool, user_pool_client)

    def _create_cognito(
        self,
        environment: str,
        config: dict[str, Any],
    ) -> tuple[cognito.UserPool, cognito.UserPoolClient]:
        """Create Cognito User Pool for operator authentication."""
        user_pool = cognito.UserPool(
            self,
            "OperatorUserPool",
            user_pool_name=f"drone-fleet-{environment}-operators",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            removal_policy=config["removal_policy"],
        )

        user_pool_client = user_pool.add_client(
            "OperatorClient",
            user_pool_client_name=f"drone-fleet-{environment}-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
        )

        return user_pool, user_pool_client

    def _build_lambda_environment(
        self,
        table: dynamodb.ITable,
        bucket: s3.IBucket,
        environment: str,
        user_pool: cognito.UserPool,
        config: dict[str, Any],
    ) -> dict[str, str]:
        """Build shared Lambda environment variables."""
        return {
            "TABLE_NAME": table.table_name,
            "BUCKET_NAME": bucket.bucket_name,
            "ENVIRONMENT": environment,
            "USER_POOL_ID": user_pool.user_pool_id,
            "BEDROCK_MODEL_ID": config.get(
                "bedrock_model_id",
                "anthropic.claude-sonnet-4-5-20250929-v1:0",
            ),
            "MAX_DRONES": str(config.get("max_drones", 5)),
        }

    def _create_lambda_functions(
        self,
        environment: str,
        config: dict[str, Any],
        lambda_environment: dict[str, str],
    ) -> None:
        """Create Lambda functions for API handlers."""
        deps_layer = lambda_.LayerVersion(
            self,
            "DependenciesLayer",
            layer_version_name=f"drone-fleet-{environment}-deps",
            description="Python dependencies for drone fleet Lambda functions",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            code=lambda_.Code.from_asset(_LAYERS_DIR),
        )

        mission_controller_log_group = logs.LogGroup(
            self,
            "MissionControllerLogGroup",
            log_group_name=f"/aws/lambda/drone-fleet-{environment}-mission-controller",
            retention=config["log_retention"],
            removal_policy=config["removal_policy"],
        )
        self.mission_controller = lambda_.Function(
            self,
            "MissionController",
            function_name=f"drone-fleet-{environment}-mission-controller",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.handlers.mission_controller.handler",
            code=lambda_.Code.from_asset(_PROJECT_ROOT, exclude=_LAMBDA_EXCLUDES),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment=lambda_environment,
            log_group=mission_controller_log_group,
            layers=[deps_layer],
        )

        mission_planner_log_group = logs.LogGroup(
            self,
            "MissionPlannerLogGroup",
            log_group_name=f"/aws/lambda/drone-fleet-{environment}-mission-planner",
            retention=config["log_retention"],
            removal_policy=config["removal_policy"],
        )
        self.mission_planner = lambda_.Function(
            self,
            "MissionPlanner",
            function_name=f"drone-fleet-{environment}-mission-planner",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.handlers.mission_planner.handler",
            code=lambda_.Code.from_asset(_PROJECT_ROOT, exclude=_LAMBDA_EXCLUDES),
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment=lambda_environment,
            log_group=mission_planner_log_group,
            layers=[deps_layer],
        )

        drone_registrar_log_group = logs.LogGroup(
            self,
            "DroneRegistrarLogGroup",
            log_group_name=f"/aws/lambda/drone-fleet-{environment}-drone-registrar",
            retention=config["log_retention"],
            removal_policy=config["removal_policy"],
        )
        self.drone_registrar = lambda_.Function(
            self,
            "DroneRegistrar",
            function_name=f"drone-fleet-{environment}-drone-registrar",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="src.handlers.drone_registrar.handler",
            code=lambda_.Code.from_asset(_PROJECT_ROOT, exclude=_LAMBDA_EXCLUDES),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment=lambda_environment,
            log_group=drone_registrar_log_group,
            layers=[deps_layer],
        )

    def _grant_permissions(
        self,
        table: dynamodb.ITable,
        bucket: s3.IBucket,
    ) -> None:
        """Grant IAM permissions to Lambda functions."""
        table.grant_read_write_data(self.mission_controller)
        table.grant_read_write_data(self.mission_planner)
        table.grant_read_write_data(self.drone_registrar)
        bucket.grant_read_write(self.mission_planner)
        bucket.grant_read(self.mission_controller)

        self.mission_planner.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )

        self.drone_registrar.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iot:CreateThing",
                    "iot:DeleteThing",
                    "iot:DescribeThing",
                    "iot:ListThings",
                    "iot:CreateKeysAndCertificate",
                    "iot:AttachThingPrincipal",
                    "iot:DetachThingPrincipal",
                    "iot:AttachPolicy",
                    "iot:DetachPolicy",
                    "iot:UpdateCertificate",
                    "iot:DeleteCertificate",
                ],
                resources=["*"],
            )
        )

        self.mission_controller.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iot:Publish", "iot:DescribeEndpoint"],
                resources=["*"],
            )
        )

    def _create_api_gateway(
        self,
        environment: str,
        config: dict[str, Any],
        user_pool: cognito.UserPool,
    ) -> None:
        """Create API Gateway with all endpoints."""
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
            authorizer_name=f"drone-fleet-{environment}-authorizer",
        )

        self._api = apigw.RestApi(
            self,
            "DroneFleetApi",
            rest_api_name=f"drone-fleet-{environment}-api",
            description=f"Drone Fleet Search API - {environment}",
            deploy_options=apigw.StageOptions(
                stage_name=environment,
                logging_level=(
                    apigw.MethodLoggingLevel.INFO
                    if config["enable_monitoring"]
                    else apigw.MethodLoggingLevel.OFF
                ),
                metrics_enabled=config["enable_monitoring"],
                tracing_enabled=config["enable_monitoring"],
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        api_v1 = self._api.root.add_resource("api").add_resource("v1")
        self._add_mission_endpoints(api_v1, authorizer)
        self._add_drone_endpoints(api_v1, authorizer)
        self._add_environment_endpoints(api_v1, authorizer)
        self._add_test_endpoints(api_v1)

    def _add_mission_endpoints(
        self,
        api_v1: apigw.Resource,
        authorizer: apigw.CognitoUserPoolsAuthorizer,
    ) -> None:
        """Add mission-related API endpoints."""
        missions = api_v1.add_resource("missions")
        missions.add_method(
            "POST",
            self._integration(self.mission_planner),
            authorizer=authorizer,
        )
        missions.add_method(
            "GET",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )

        mission = missions.add_resource("{mission_id}")
        mission.add_method(
            "GET",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )

        mission.add_resource("approve").add_method(
            "POST",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )
        mission.add_resource("abort").add_method(
            "POST",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )
        mission.add_resource("status").add_method(
            "GET",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )

        detections = mission.add_resource("detections")
        detections.add_method(
            "GET",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )
        detection = detections.add_resource("{detection_id}")
        detection.add_resource("review").add_method(
            "POST",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )

    def _add_drone_endpoints(
        self,
        api_v1: apigw.Resource,
        authorizer: apigw.CognitoUserPoolsAuthorizer,
    ) -> None:
        """Add drone-related API endpoints."""
        drones = api_v1.add_resource("drones")
        drones.add_method(
            "GET",
            self._integration(self.drone_registrar),
            authorizer=authorizer,
        )

        drone = drones.add_resource("{drone_id}")
        drone.add_method(
            "GET",
            self._integration(self.drone_registrar),
            authorizer=authorizer,
        )
        drone.add_resource("recall").add_method(
            "POST",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )

    def _add_environment_endpoints(
        self,
        api_v1: apigw.Resource,
        authorizer: apigw.CognitoUserPoolsAuthorizer,
    ) -> None:
        """Add environment-related API endpoints."""
        environments = api_v1.add_resource("environments")
        environments.add_method(
            "POST",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )
        environments.add_resource("{environment_id}").add_method(
            "GET",
            self._integration(self.mission_controller),
            authorizer=authorizer,
        )

    @staticmethod
    def _integration(function: lambda_.Function) -> apigw.LambdaIntegration:
        """Create a LambdaIntegration for the given function.

        CDK type stubs incorrectly declare Function as incompatible with IFunction.
        """
        return apigw.LambdaIntegration(function)  # type: ignore[arg-type]

    def _add_test_endpoints(self, api_v1: apigw.Resource) -> None:
        """Add test endpoints (no auth for integration testing)."""
        test = api_v1.add_resource("test")
        test_scenarios = test.add_resource("scenarios")
        test_scenarios.add_method(
            "POST",
            self._integration(self.mission_controller),
        )
        test_scenario = test_scenarios.add_resource("{scenario_id}")
        test_scenario.add_resource("results").add_method(
            "GET",
            self._integration(self.mission_controller),
        )

    def _create_outputs(
        self,
        environment: str,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
    ) -> None:
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            "ApiEndpointOutput",
            value=self._api.url,
            description=f"API Gateway endpoint for {environment}",
            export_name=f"DroneFleet-{environment}-ApiEndpoint",
        )

        CfnOutput(
            self,
            "UserPoolIdOutput",
            value=user_pool.user_pool_id,
            description=f"Cognito User Pool ID for {environment}",
            export_name=f"DroneFleet-{environment}-UserPoolId",
        )

        CfnOutput(
            self,
            "UserPoolClientIdOutput",
            value=user_pool_client.user_pool_client_id,
            description=f"Cognito User Pool Client ID for {environment}",
            export_name=f"DroneFleet-{environment}-UserPoolClientId",
        )
