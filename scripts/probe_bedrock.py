"""
Pre-demo Bedrock availability probe (`make probe-bedrock`).

This account's Bedrock on-demand quotas are dynamically adjusted and routinely
sit at an effective 0 (ADR 008 + addendum) — and because the orchestrator
degrades gracefully, a fully throttled account still *looks* healthy while
never touching Bedrock. Run this before recording the demo to know whether
the live embed/reasoning path will fire, and from which region.

Makes exactly one InvokeModel (Titan embed) and one Converse (configured
reasoning model) per candidate region, retries disabled — negligible token
spend, fast failure.

Usage:
    python scripts/probe_bedrock.py                    # probe candidate regions
    python scripts/probe_bedrock.py --region eu-north-1  # probe one region
"""
import argparse
import json
import os
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402

# EU regions the eu.* cross-region profiles can be invoked from, plus us-west-2
# as the out-of-geo fallback candidate (us.* profile).
CANDIDATE_REGIONS = ["eu-north-1", "eu-west-1", "eu-central-1", "eu-west-3", "us-west-2"]

_PROBE_CONFIG = Config(
    connect_timeout=5, read_timeout=25, retries={"max_attempts": 1, "mode": "standard"}
)


def _reasoning_model_for(region: str) -> str:
    model = settings.bedrock_reasoning_model_id
    # eu.* inference profiles aren't invocable from US regions and vice versa.
    if not region.startswith("eu-") and model.startswith("eu."):
        return "us." + model.removeprefix("eu.")
    return model


def _outcome(fn) -> str:
    start = time.monotonic()
    try:
        fn()
        return f"OK ({time.monotonic() - start:.1f}s)"
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        message = exc.response["Error"].get("Message", "")
        return f"{code}: {message[:100]}"
    except Exception as exc:  # noqa: BLE001 — a probe reports, it doesn't crash
        return f"{type(exc).__name__}: {str(exc)[:100]}"


def probe_region(region: str) -> None:
    client = boto3.client("bedrock-runtime", region_name=region, config=_PROBE_CONFIG)
    embed_body = json.dumps({"inputText": "probe", "dimensions": 256, "normalize": True})
    reasoning_model = _reasoning_model_for(region)

    print(f"\n=== {region} ===")
    print(f"  {settings.bedrock_embedding_model_id}: " + _outcome(
        lambda: client.invoke_model(modelId=settings.bedrock_embedding_model_id, body=embed_body)
    ))
    print(f"  {reasoning_model}: " + _outcome(
        lambda: client.converse(
            modelId=reasoning_model,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: ok"}]}],
            inferenceConfig={"maxTokens": 8},
        )
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", help="probe a single region instead of the candidate list")
    args = parser.parse_args()

    regions = [args.region] if args.region else CANDIDATE_REGIONS
    print(f"Configured BEDROCK_REGION: {settings.bedrock_region}")
    for candidate in regions:
        probe_region(candidate)
    print("\nAll throttled? The clamp is account-level (ADR 008 addendum) — the demo still")
    print("works on deterministic fallbacks; set BEDROCK_REGION to any region that shows OK.")
