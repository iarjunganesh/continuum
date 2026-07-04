"""
Central configuration for Continuum. All secrets/config loaded from environment
variables only — never hardcode credentials here. See .env.example.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # CockroachDB
    cockroach_database_url: str
    cockroach_mcp_endpoint: str = "https://cockroachlabs.cloud/mcp"
    cockroach_mcp_api_key: str = ""

    # ccloud CLI (stretch — ADR 004)
    ccloud_api_key: str = ""
    ccloud_cluster_id: str = ""

    # AWS
    aws_region: str = "us-east-1"
    # Titan Text Embeddings V2 — outputs 256/512/1024 dims; must match
    # infra/schema.sql VECTOR(1024) and embedding_dimensions below.
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_dimensions: int = 1024
    # Claude on Bedrock via a cross-region inference profile. Verify the exact
    # ID under Bedrock console -> Model access before the demo.
    bedrock_reasoning_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    lambda_function_name: str = "continuum-orchestrator"

    # Remediation loop — each incident resolves after max_remediation_steps
    # executed steps; each step's simulated execution takes
    # step_execution_seconds (the window in which chaos_kill.py strikes).
    max_remediation_steps: int = 3
    step_execution_seconds: float = 5.0

    # App
    app_env: str = "local"
    log_level: str = "INFO"


settings = Settings()
