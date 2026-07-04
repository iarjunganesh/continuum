"""
AWS Lambda deployment wrapper. The actual logic lives in agents/orchestrator.py
(lambda_handler) — this module exists as the deployment package's entrypoint
target referenced in template.yaml, kept separate so orchestrator.py stays
testable outside of a Lambda runtime.
"""
from agents.orchestrator import lambda_handler  # noqa: F401  (re-exported for SAM)
