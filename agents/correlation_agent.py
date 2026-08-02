"""
Correlation Agent — embeds an incoming alert via Amazon Bedrock (Titan Text
Embeddings V2) and finds semantically similar past incidents via CockroachDB's
native vector search (C-SPANN index).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

import boto3
import psycopg
from botocore.config import Config
from psycopg.rows import dict_row

from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)

# Tight timeouts + capped retries: this client runs inside a Lambda with a
# finite invocation budget, and the botocore defaults (60s read timeout,
# backoff retries) can consume all of it when Bedrock throttles — and Bedrock
# quotas are dynamic, so throttling is always a live possibility regardless of
# what the last probe showed (ADR 008 + addenda). Fail fast and let
# the orchestrator's best-effort handling degrade to "no precedent".
_BEDROCK_CLIENT_CONFIG = Config(
    connect_timeout=5,
    read_timeout=15,
    retries={"max_attempts": 2, "mode": "standard"},
)


@dataclass
class CorrelationMatch:
    incident_id: str
    summary: str
    state: str
    distance: float


class CorrelationAgent:
    def __init__(self, dsn: str | None = None):
        self._dsn = dsn or settings.cockroach_database_url
        self._bedrock = None  # lazy — unit tests never touch AWS

    def _client(self):
        if self._bedrock is None:
            self._bedrock = boto3.client(
                "bedrock-runtime",
                region_name=settings.bedrock_region,
                config=_BEDROCK_CLIENT_CONFIG,
            )
        return self._bedrock

    def embed(self, alert_text: str) -> List[float]:
        """Amazon Bedrock — Titan Text Embeddings V2. Dimensions must match
        infra/schema.sql VECTOR(1024)."""
        body = json.dumps(
            {
                "inputText": alert_text,
                "dimensions": settings.embedding_dimensions,
                "normalize": True,
            }
        )
        response = self._client().invoke_model(modelId=settings.bedrock_embedding_model_id, body=body)
        embedding = json.loads(response["body"].read())["embedding"]
        log.info("alert_embedded", model=settings.bedrock_embedding_model_id, dimensions=len(embedding))
        return embedding

    def find_similar(self, service: str, embedding: List[float], k: int = 5) -> List[CorrelationMatch]:
        vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        with psycopg.connect(self._dsn) as conn, conn.cursor(row_factory=dict_row) as cur:
            # THE CTE IS LOAD-BEARING — do not inline this back into a single
            # SELECT with a JOIN. Joining `incidents` in the same statement as
            # the `<->` ordering makes CockroachDB abandon the C-SPANN index and
            # fall back to `spans: FULL SCAN` over incident_embeddings. Verified
            # with EXPLAIN: with the JOIN inlined the plan never mentions
            # idx_incident_embedding; with the ANN search isolated in this CTE
            # the plan shows `vector search ... prefix spans: [/'<service>']`.
            #
            # That made the whole "Distributed Vector Indexing" claim untrue for
            # a while, silently — the query returned correct results either way,
            # just by scanning everything. tests/integration/test_vector_index.py
            # asserts the plan, because no unit test can (psycopg is mocked at
            # the import boundary, so SQL text changes go unnoticed).
            cur.execute(
                """
                WITH nearest AS (
                    SELECT incident_id, embedding <-> %s::vector AS distance
                    FROM incident_embeddings
                    WHERE service = %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s
                )
                SELECT n.incident_id, i.summary, i.state, n.distance
                FROM nearest n
                JOIN incidents i ON i.incident_id = n.incident_id
                ORDER BY n.distance
                """,
                (vector_literal, service, vector_literal, k),
            )
            matches = [
                CorrelationMatch(
                    incident_id=str(row["incident_id"]),
                    summary=row["summary"],
                    state=row["state"],
                    distance=float(row["distance"]),
                )
                for row in cur.fetchall()
            ]
            log.info("correlation_query", service=service, matches_found=len(matches))
            return matches
