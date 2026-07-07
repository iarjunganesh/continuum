-- Continuum — CockroachDB schema
-- Dual memory model: transactional incident/remediation state + vector embeddings
-- for semantic correlation, in a single distributed SQL store.
--
-- Vector index syntax follows CockroachDB's C-SPANN vector indexing (v25.2+, in preview).
-- Ref: https://www.cockroachlabs.com/docs/stable/vector-indexes
-- On self-managed clusters you may need:
--   SET CLUSTER SETTING feature.vector_index.enabled = true;
-- Managed CockroachDB Cloud clusters used for this hackathon should have this
-- available by default — verify against the current CockroachDB Cloud docs at build time.

CREATE TABLE IF NOT EXISTS incidents (
    incident_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id    STRING NOT NULL,           -- groups repeated alerts for the same live incident
    service           STRING NOT NULL,
    region            STRING NOT NULL DEFAULT 'default',
    severity          STRING NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    state             STRING NOT NULL DEFAULT 'open'
                        CHECK (state IN ('open','correlating','remediating','resolved','escalated')),
    summary           STRING,
    opened_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at       TIMESTAMPTZ,
    synthetic         BOOL NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents (state);
CREATE INDEX IF NOT EXISTS idx_incidents_correlation ON incidents (correlation_id);

-- Remediation log. One row per (incident, step_index) — rows are never deleted.
-- A forward step is claimed at 'executing' via INSERT ... ON CONFLICT DO NOTHING
-- (so a racing invocation can't create a duplicate), then advances in place to
-- 'executed'; a resuming agent re-sets an interrupted step back to 'executing'.
-- The UNIQUE (incident_id, step_index) below is what makes that claim atomic, so
-- a resuming agent replays this log to know exactly which steps already ran and
-- whether the last one was interrupted mid-execution. See ADR 009.
CREATE TABLE IF NOT EXISTS remediation_steps (
    step_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id       UUID NOT NULL REFERENCES incidents(incident_id),
    step_index        INT NOT NULL,
    action            STRING NOT NULL,
    proposed_by       STRING NOT NULL DEFAULT 'remediation_agent',
    status            STRING NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','executing','executed','failed','skipped')),
    detail            JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (incident_id, step_index)
);

CREATE INDEX IF NOT EXISTS idx_remediation_incident ON remediation_steps (incident_id, step_index);

-- Semantic memory: one embedding per incident for nearest-neighbor correlation.
-- 1024 dims matches Amazon Titan Text Embeddings V2 (amazon.titan-embed-text-v2:0),
-- which outputs 256/512/1024 dims — keep in sync with config.py embedding_dimensions.
CREATE TABLE IF NOT EXISTS incident_embeddings (
    incident_id       UUID PRIMARY KEY REFERENCES incidents(incident_id),
    service           STRING NOT NULL,
    region            STRING NOT NULL DEFAULT 'default',
    embedding         VECTOR(1024) NOT NULL,
    embedding_model   STRING NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vector index, prefixed by service so ANN search is naturally partitioned
-- per-service rather than scanning the full cross-service corpus.
CREATE VECTOR INDEX IF NOT EXISTS idx_incident_embedding
    ON incident_embeddings (service, embedding);

-- Example correlation query (used by correlation_agent.py):
--
-- SELECT e.incident_id, i.summary, i.state,
--        e.embedding <-> $1 AS distance
-- FROM incident_embeddings e
-- JOIN incidents i ON i.incident_id = e.incident_id
-- WHERE e.service = $2
-- ORDER BY e.embedding <-> $1
-- LIMIT 5;

-- Recovery query (used by orchestrator.py on every cold start — see ARCHITECTURE.md §3).
-- Returns the open incident for a correlation_id plus its LATEST remediation step's
-- index and status, so a resuming invocation knows whether the previous one died
-- mid-step ('executing') or finished it ('executed'):
--
-- SELECT i.incident_id, i.correlation_id, i.service, i.state,
--        s.step_index AS last_step_index, s.status AS last_step_status
-- FROM incidents i
-- LEFT JOIN remediation_steps s ON s.incident_id = i.incident_id
--     AND s.step_index = (SELECT max(step_index) FROM remediation_steps
--                         WHERE incident_id = i.incident_id)
-- WHERE i.correlation_id = $1 AND i.state NOT IN ('resolved','escalated')
-- ORDER BY i.opened_at DESC
-- LIMIT 1;
