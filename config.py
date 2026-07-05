"""
Central configuration for Continuum. All secrets/config loaded from environment
variables only — never hardcode credentials here. See .env.example.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY (read by boto3's
    # own credential chain, never by this class) and any other ambient env
    # var must not crash Settings() at import time — pydantic-settings
    # defaults to extra="forbid", which turns "this shell happens to have
    # AWS creds exported" into an app-wide startup failure.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # CockroachDB
    cockroach_database_url: str
    cockroach_mcp_endpoint: str = "https://cockroachlabs.cloud/mcp"
    cockroach_mcp_api_key: str = ""

    # ccloud CLI (stretch — ADR 004)
    ccloud_api_key: str = ""
    ccloud_cluster_id: str = ""

    # AWS — eu-central-1 co-locates the Lambda with the CockroachDB Cloud
    # cluster used for this build (see docs/adr/007-eu-central-1-region.md).
    aws_region: str = "eu-central-1"
    # bedrock-runtime clients call THIS region, not aws_region — this account
    # has a hard 0 on-demand/cross-region quota for every Bedrock model in
    # eu-central-1 (and us-east-1), and that quota isn't self-service
    # adjustable. eu-west-1 already has full default quota. See ADR 008;
    # Lambda + CockroachDB stay in eu-central-1 (ADR 007) — only the Bedrock
    # calls cross regions.
    bedrock_region: str = "eu-west-1"
    # Titan Text Embeddings V2 — outputs 256/512/1024 dims; must match
    # infra/schema.sql VECTOR(1024) and embedding_dimensions below.
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_dimensions: int = 1024
    # Claude Sonnet 4.5 via the EU cross-region inference profile. Verify the
    # exact ID under Bedrock console -> Cross-region inference before the demo.
    bedrock_reasoning_model_id: str = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
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
