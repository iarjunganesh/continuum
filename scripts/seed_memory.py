"""
Loads synthetic incidents into CockroachDB — the transactional `incidents`
table, the historical `remediation_steps` each resolved incident took (so
the Remediation Agent has real precedent to replay), and, via Bedrock
embeddings, the `incident_embeddings` vector table. Run after `make migrate`.

Usage:
    python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl
"""
import argparse
import json
import os
import sys
import time

import psycopg
from botocore.exceptions import ClientError
from psycopg.types.json import Json

# Running as `python scripts/seed_memory.py` puts scripts/ (not the repo
# root) on sys.path, so agents/config/observability won't import otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.correlation_agent import CorrelationAgent  # noqa: E402
from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)

# New/low-volume Bedrock accounts throttle on-demand embedding calls well
# below the account's published per-minute quota (ADR 008) — a flat 1s sleep
# isn't enough headroom, so back off exponentially on ThrottlingException
# instead of failing the whole run on the first busy moment.
EMBED_MAX_RETRIES = 6
EMBED_BACKOFF_BASE_SECONDS = 5.0


def _embed_with_retry(correlation: CorrelationAgent, text: str) -> list[float]:
    for attempt in range(EMBED_MAX_RETRIES):
        try:
            return correlation.embed(text)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ThrottlingException":
                raise
            wait = EMBED_BACKOFF_BASE_SECONDS * (2 ** attempt)
            log.warning("embed_throttled_retrying", attempt=attempt + 1, wait_seconds=wait)
            time.sleep(wait)
    raise RuntimeError(f"Bedrock embedding still throttled after {EMBED_MAX_RETRIES} retries")


def seed(file_path: str):
    correlation = CorrelationAgent()
    with open(file_path, encoding="utf-8") as f, \
         psycopg.connect(settings.cockroach_database_url) as conn:
        cur = conn.cursor()
        count = 0
        for line in f:
            rec = json.loads(line)
            cur.execute(
                """
                INSERT INTO incidents (incident_id, correlation_id, service, region,
                                        severity, state, summary, opened_at, synthetic)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
                ON CONFLICT (incident_id) DO NOTHING
                """,
                (rec["incident_id"], rec["correlation_id"], rec["service"], rec["region"],
                 rec["severity"], rec["state"], rec["summary"], rec["opened_at"]),
            )
            # Historical remediation path — the precedent a live incident replays.
            for idx, action in enumerate(rec.get("remediation_steps", [])):
                cur.execute(
                    """
                    INSERT INTO remediation_steps (incident_id, step_index, action, status, detail)
                    VALUES (%s, %s, %s, 'executed', %s)
                    ON CONFLICT (incident_id, step_index) DO NOTHING
                    """,
                    (rec["incident_id"], idx, action, Json({"seeded": True})),
                )
            embedding = _embed_with_retry(correlation, rec["summary"])
            vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
            cur.execute(
                """
                INSERT INTO incident_embeddings (incident_id, service, region, embedding, embedding_model)
                VALUES (%s, %s, %s, %s::vector, %s)
                ON CONFLICT (incident_id) DO NOTHING
                """,
                (rec["incident_id"], rec["service"], rec["region"], vector_literal,
                 settings.bedrock_embedding_model_id),
            )
            conn.commit()  # commit per record — a later throttle must not roll back seeded rows
            count += 1
            time.sleep(1.0)  # space out Bedrock calls — default on-demand TPS
        log.info("seed_complete", records=count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    seed(args.file)
