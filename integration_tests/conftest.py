"""Integration test configuration and fixtures."""

import os

import boto3
import pytest

API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    "https://786xab9jg3.execute-api.us-east-1.amazonaws.com/development",
)
USER_POOL_ID = os.environ.get("USER_POOL_ID", "us-east-1_qcs5Z4lge")
USER_POOL_CLIENT_ID = os.environ.get("USER_POOL_CLIENT_ID", "3rob9jl7brf06jroi912mbnbv9")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "chris-dev")

TEST_USERNAME = os.environ.get("TEST_USERNAME", "inttest@drone-fleet.test")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "IntTest!2024#Secure")


def _get_cognito_client():
    """Get a Cognito IDP client."""
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    return session.client("cognito-idp")


def _ensure_test_user_exists():
    """Create the integration test user if it doesn't exist."""
    client = _get_cognito_client()
    try:
        client.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=TEST_USERNAME,
        )
    except client.exceptions.UserNotFoundException:
        client.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=TEST_USERNAME,
            UserAttributes=[
                {"Name": "email", "Value": TEST_USERNAME},
                {"Name": "email_verified", "Value": "true"},
            ],
            TemporaryPassword=TEST_PASSWORD,
            MessageAction="SUPPRESS",
        )
        # Set permanent password (moves user to CONFIRMED state)
        client.admin_set_user_password(
            UserPoolId=USER_POOL_ID,
            Username=TEST_USERNAME,
            Password=TEST_PASSWORD,
            Permanent=True,
        )


def _get_auth_token() -> str:
    """Authenticate and return an ID token."""
    client = _get_cognito_client()
    _ensure_test_user_exists()

    response = client.initiate_auth(
        ClientId=USER_POOL_CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": TEST_USERNAME,
            "PASSWORD": TEST_PASSWORD,
        },
    )
    return response["AuthenticationResult"]["IdToken"]


@pytest.fixture(scope="session")
def api_url() -> str:
    """Get the API base URL."""
    return API_BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def auth_token() -> str:
    """Get an authentication token for API calls."""
    return _get_auth_token()


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> dict[str, str]:
    """Get headers with authentication token."""
    return {
        "Authorization": auth_token,
        "Content-Type": "application/json",
    }
