from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Global configuration for the Clarity Agent.
    This class automatically reads values from environment variables or a .env file,
    making the application configurable and secure.
    """

    # --- AWS Configuration ---
    # The SSO profile name created via `aws configure sso`
    aws_profile_name: str = "AdministratorAccess-158667298965"
    # The primary region for AWS services, especially Bedrock
    aws_region_name: str = "us-east-1"

    # --- Bedrock Model Configuration ---
    # NOTE: We are using Amazon's Titan model as it's guaranteed to be available
    # in the hackathon AWS account and does not require a special use-case form.
    bedrock_model_id: str = "amazon.titan-text-express-v1"

    # --- MCP Server Configuration ---
    # The host and port where our local MCP server will run
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8001

    # --- Model Behavior Controls ---
    # These parameters are passed to the Bedrock model to control its output
    max_tokens: int = 4096
    temperature: float = 0.5  # Lower temperature for more factual, less creative responses
    top_p: float = 0.9        # Standard value for nucleus sampling

    class Config:
        # Specifies that settings can be loaded from a .env file
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single, global instance of the settings to be used across the application
settings = Settings()