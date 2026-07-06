"""
Capture real Amazon Titan embeddings ONCE into a committed fixture, so seeding
(and the demo Space) no longer needs a live Bedrock call on every run.

Run this from any environment where Bedrock IS reachable (e.g. an AWS account
without the throttle described in ADR 008); commit the resulting JSON; then
everyone else seeds honest, semantically-ranked vectors offline with:

    python scripts/seed_memory.py --file <jsonl> --from-fixture <out.json>

Usage:
    python scripts/capture_seed_embeddings.py \
        --file data/synthetic/incidents_seed.jsonl \
        --out  data/synthetic/seed_embeddings.json
"""
import argparse
import json
import os
import sys

# Running as `python scripts/capture_seed_embeddings.py` puts scripts/ (not the
# repo root) on sys.path, so agents/config/observability won't import otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_memory import _embed_with_retry  # noqa: E402  (reuse the retry/backoff)

from agents.correlation_agent import CorrelationAgent  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)


def capture(file_path: str, out_path: str) -> None:
    correlation = CorrelationAgent()
    embeddings: dict[str, list[float]] = {}
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            embeddings[rec["incident_id"]] = _embed_with_retry(correlation, rec["summary"])
            log.info("embedding_captured", incident_id=rec["incident_id"],
                     captured=len(embeddings))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out:
        json.dump(embeddings, out)
    log.info("capture_complete", records=len(embeddings), out=out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--out", default="data/synthetic/seed_embeddings.json")
    args = parser.parse_args()
    capture(args.file, args.out)
