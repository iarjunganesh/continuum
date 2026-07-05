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
from psycopg.rows import dict_row

from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)


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
            self._bedrock = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        return self._bedrock

    def embed(self, alert_text: str) -> List[float]:
        """Amazon Bedrock — Titan Text Embeddings V2. Dimensions must match
        infra/schema.sql VECTOR(1024)."""
        body = json.dumps({
            "inputText": alert_text,
            "dimensions": settings.embedding_dimensions,
            "normalize": True,
        })
        response = self._client().invoke_model(
            modelId=settings.bedrock_embedding_model_id, body=body
        )
        embedding = json.loads(response["body"].read())["embedding"]
        log.info("alert_embedded", model=settings.bedrock_embedding_model_id,
                 dimensions=len(embedding))
        return embedding

    def find_similar(self, service: str, embedding: List[float], k: int = 5) -> List[CorrelationMatch]:
        vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        with psycopg.connect(self._dsn) as conn, \
             conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT e.incident_id, i.summary, i.state,
                       e.embedding <-> %s::vector AS distance
                FROM incident_embeddings e
                JOIN incidents i ON i.incident_id = e.incident_id
                WHERE e.service = %s
                ORDER BY e.embedding <-> %s::vector
                LIMIT %s
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
