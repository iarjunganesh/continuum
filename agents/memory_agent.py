"""
Memory Agent — the ONLY module permitted to write incident/remediation state.

See CLAUDE.md: every write to `incidents` or `remediation_steps` must go
through here. This single-write-path property is what keeps the recovery
guarantee in ARCHITECTURE.md §3 honest — there's exactly one place state
changes happen, so a resuming Lambda invocation can trust what it reads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from config import settings
from observability.structured_logger import get_logger

log = get_logger(__name__)


@dataclass
class IncidentState:
    incident_id: UUID
    correlation_id: str
    service: str
    state: str
    last_step_index: Optional[int]
    last_step_status: Optional[str]


class MemoryAgent:
    def __init__(self, dsn: str | None = None):
        self._dsn = dsn or settings.cockroach_database_url

    def _conn(self):
        return psycopg.connect(self._dsn)

    # --- Recovery read (called first, on every orchestrator invocation) ---
    def get_open_incident(self, correlation_id: str) -> Optional[IncidentState]:
        """
        The recovery query described in ARCHITECTURE.md §3.
        MUST be called before any new reasoning happens in the orchestrator.
        Returns the latest step's index AND status so a resuming invocation
        knows whether the previous one died mid-step.
        """
        with self._conn() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT i.incident_id, i.correlation_id, i.service, i.state,
                       s.step_index AS last_step_index, s.status AS last_step_status
                FROM incidents i
                LEFT JOIN remediation_steps s ON s.incident_id = i.incident_id
                    AND s.step_index = (
                        SELECT max(step_index) FROM remediation_steps
                        WHERE incident_id = i.incident_id
                    )
                WHERE i.correlation_id = %s AND i.state NOT IN ('resolved', 'escalated')
                ORDER BY i.opened_at DESC
                LIMIT 1
                """,
                (correlation_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            log.info("recovered_incident_state", correlation_id=correlation_id, state=row["state"],
                      last_step_index=row["last_step_index"], last_step_status=row["last_step_status"])
            return IncidentState(**row)

    # --- Writes ---
    def open_incident(self, correlation_id: str, service: str, region: str,
                       severity: str, summary: str) -> UUID:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incidents (correlation_id, service, region, severity, summary, state)
                VALUES (%s, %s, %s, %s, %s, 'open')
                RETURNING incident_id
                """,
                (correlation_id, service, region, severity, summary),
            )
            incident_id = cur.fetchone()[0]
            conn.commit()
            log.info("incident_opened", incident_id=str(incident_id), correlation_id=correlation_id)
            return incident_id

    def set_state(self, incident_id: UUID, state: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            if state == "resolved":
                cur.execute(
                    "UPDATE incidents SET state = 'resolved', updated_at = now(), "
                    "resolved_at = now() WHERE incident_id = %s",
                    (incident_id,),
                )
            else:
                cur.execute(
                    "UPDATE incidents SET state = %s, updated_at = now() WHERE incident_id = %s",
                    (state, incident_id),
                )
            conn.commit()
            log.info("incident_state_changed", incident_id=str(incident_id), state=state)

    def log_step(self, incident_id: UUID, step_index: int, action: str,
                 status: str = "proposed", detail: dict | None = None) -> None:
        """Insert a step row, or advance its status if the row already exists
        (proposed -> executing -> executed). Rows are never deleted."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO remediation_steps (incident_id, step_index, action, status, detail)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (incident_id, step_index) DO UPDATE SET status = EXCLUDED.status
                """,
                (incident_id, step_index, action, status, Json(detail or {})),
            )
            conn.commit()
            log.info("remediation_step_logged", incident_id=str(incident_id),
                      step_index=step_index, status=status)

    def set_step_status(self, incident_id: UUID, step_index: int, status: str) -> None:
        """Advance an existing step's status. Committed BEFORE and AFTER the
        simulated execution so a kill mid-execution leaves status='executing'
        durably in CockroachDB — the fingerprint the next invocation reads."""
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE remediation_steps SET status = %s WHERE incident_id = %s AND step_index = %s",
                (status, incident_id, step_index),
            )
            conn.commit()
            log.info("remediation_step_status", incident_id=str(incident_id),
                      step_index=step_index, status=status)
