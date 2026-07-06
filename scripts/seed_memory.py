"""
Loads synthetic incidents into CockroachDB — the transactional `incidents`
table, the historical `remediation_steps` each resolved incident took (so
the Remediation Agent has real precedent to replay), and the
`incident_embeddings` vector table. Run after `make migrate`.

The embedding for each incident comes from one of three sources:
    (default)        live Amazon Bedrock (Titan v2), with retry/backoff
    --from-fixture   precomputed real Titan vectors (see capture_seed_embeddings.py)
    --no-embeddings  deterministic Bedrock-free vectors (synthetic_vectors.py)

The last two need no AWS credentials and let the demo Space render populated
even while this account's Bedrock quota is throttled (ADR 008).

Usage:
    python scripts/seed_memory.py --file data/synthetic/incidents_seed.jsonl
    python scripts/seed_memory.py --file ... --from-fixture data/synthetic/seed_embeddings.json
    python scripts/seed_memory.py --file ... --no-embeddings
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

from synthetic_vectors import deterministic_embedding  # noqa: E402

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


def _resolve_embedding(rec, mode, correlation, fixture):
    """Return the embedding for a record from the chosen source."""
    if mode == "no-embeddings":
        return deterministic_embedding(rec["summary"])
    if mode == "fixture":
        emb = fixture.get(rec["incident_id"])
        if emb is None:
            log.warning("fixture_missing_embedding", incident_id=rec["incident_id"])
            return deterministic_embedding(rec["summary"])
        return emb
    return _embed_with_retry(correlation, rec["summary"])  # live Bedrock


def seed(file_path: str, mode: str = "live", fixture_path: str | None = None):
    correlation = CorrelationAgent() if mode == "live" else None
    fixture: dict = {}
    if mode == "fixture":
        with open(fixture_path, encoding="utf-8") as ff:
            fixture = json.load(ff)
    model_label = settings.bedrock_embedding_model_id if mode != "no-embeddings" else "synthetic-deterministic"
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
            embedding = _resolve_embedding(rec, mode, correlation, fixture)
            vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
            cur.execute(
                """
                INSERT INTO incident_embeddings (incident_id, service, region, embedding, embedding_model)
                VALUES (%s, %s, %s, %s::vector, %s)
                ON CONFLICT (incident_id) DO NOTHING
                """,
                (rec["incident_id"], rec["service"], rec["region"], vector_literal, model_label),
            )
            conn.commit()  # commit per record — a later throttle must not roll back seeded rows
            count += 1
            if mode == "live":
                time.sleep(1.0)  # space out Bedrock calls — default on-demand TPS
        log.info("seed_complete", records=count, embedding_source=mode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-fixture", metavar="PATH",
                        help="load precomputed real Titan vectors (capture_seed_embeddings.py)")
    source.add_argument("--no-embeddings", action="store_true",
                        help="deterministic Bedrock-free vectors — no AWS credentials needed")
    args = parser.parse_args()
    if args.no_embeddings:
        seed(args.file, mode="no-embeddings")
    elif args.from_fixture:
        seed(args.file, mode="fixture", fixture_path=args.from_fixture)
    else:
        seed(args.file)
