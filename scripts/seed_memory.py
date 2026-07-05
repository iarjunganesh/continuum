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
from psycopg.types.json import Json

# Running as `python scripts/seed_memory.py` puts scripts/ (not the repo
# root) on sys.path, so agents/config/observability won't import otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.correlation_agent import CorrelationAgent  # noqa: E402
from config import settings  # noqa: E402
from observability.structured_logger import get_logger  # noqa: E402

log = get_logger(__name__)


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
            embedding = correlation.embed(rec["summary"])
            time.sleep(1.0)  # space out Bedrock calls — default on-demand TPS
            # quotas throttle a tight back-to-back loop even after boto3's own retries
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
            count += 1
        conn.commit()
        log.info("seed_complete", records=count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    seed(args.file)
