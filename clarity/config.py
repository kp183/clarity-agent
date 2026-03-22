from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """
    Global configuration for Clarity.
    All values can be overridden via environment variables or a .env file.
    """

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- AWS Configuration ---
    aws_profile_name: str = "default"
    aws_region_name: str = "us-east-1"

    # --- Bedrock Model ---
    bedrock_model_id: str = "amazon.titan-text-express-v1"

    # --- Groq ---
    llm_provider: str = "bedrock"   # "bedrock" or "groq"
    groq_api_key: str = ""
    groq_model_id: str = "llama-3.3-70b-versatile"

    # --- MCP Server ---
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8001

    # --- Model Behavior ---
    max_tokens: int = 4096
    temperature: float = 0.3
    top_p: float = 0.9

    # --- Database ---
    database_url: str = "sqlite:///clarity.db"

    # --- Monitoring ---
    monitoring_interval_seconds: int = 30
    alert_threshold_error_rate: float = 0.15

    # --- Application ---
    debug: bool = False
    log_level: str = "INFO"

    # --- Security ---
    jwt_secret_key: str = ""
    auth_enabled: bool = False

    # --- Optional Integrations ---
    slack_webhook_url: str = ""
    jira_base_url: str = ""
    jira_project_key: str = "INC"
    jira_email: str = ""
    jira_api_token: str = ""

    # --- Error Monitoring ---
    sentry_dsn: str = ""


settings = Settings()
