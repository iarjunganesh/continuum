"""
Continuum demo UI — live incident feed + recovery visualization.

Reads live from CockroachDB. Intended for the recorded demo video
(docs/DEMO_RUNBOOK.md) and the public Hugging Face Space, not production.
"""
import asyncio
import json

import gradio as gr
import psycopg
from psycopg.rows import dict_row

from agents.query_agent import QueryAgent
from config import settings

query_agent = QueryAgent()


def fetch_incidents():
    with psycopg.connect(settings.cockroach_database_url) as conn, \
         conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT i.incident_id, i.service, i.region, i.severity, i.state,
                   count(s.step_id) AS steps_logged,
                   max(s.step_index) AS last_step,
                   (SELECT s2.status FROM remediation_steps s2
                    WHERE s2.incident_id = i.incident_id
                    ORDER BY s2.step_index DESC LIMIT 1) AS last_step_status
            FROM incidents i
            LEFT JOIN remediation_steps s ON s.incident_id = i.incident_id
            GROUP BY i.incident_id, i.service, i.region, i.severity, i.state
            ORDER BY i.updated_at DESC
            LIMIT 50
            """
        )
        rows = cur.fetchall()
    return [[str(r["incident_id"])[:8], r["service"], r["region"], r["severity"],
             r["state"], r["steps_logged"], r["last_step"], r["last_step_status"]]
            for r in rows]


def ask_via_mcp():
    """Runs the live query-interface beat through the CockroachDB Cloud
    Managed MCP Server (read-only) instead of a direct psycopg connection —
    the same table above, but driven over MCP so the demo can show both
    paths hitting the same durable state (ADR 003)."""
    try:
        result = asyncio.run(query_agent.list_open_incidents())
    except Exception as exc:  # MCP endpoint unreachable/misconfigured
        return f"MCP query failed: {exc}"
    return json.dumps(result.rows, indent=2, default=str)


with gr.Blocks(title="Continuum — Live Incident Memory") as demo:
    gr.Markdown("# 🔁 Continuum\nAgentic memory for incident response — CockroachDB × AWS Hackathon 2026")
    gr.Markdown(
        "Every row below is read live from CockroachDB. Kill the orchestrator mid-incident "
        "(`scripts/chaos_kill.py`) and refresh — the step it died on stays `executing`, "
        "and the next invocation resumes exactly there. State persists; the process doesn't."
    )
    table = gr.Dataframe(
        headers=["Incident", "Service", "Region", "Severity", "State",
                 "Steps Logged", "Last Step", "Last Step Status"],
        label="Incidents (live from CockroachDB)",
    )
    refresh_btn = gr.Button("Refresh")
    refresh_btn.click(fn=fetch_incidents, outputs=table)
    demo.load(fn=fetch_incidents, outputs=table)

    gr.Markdown(
        "## Ask via CockroachDB Managed MCP Server\n"
        "Same durable state, queried over MCP (read-only) instead of a direct connection."
    )
    mcp_output = gr.Code(label="Open incidents (via MCP)", language="json")
    mcp_btn = gr.Button("Ask via MCP: what's open right now?")
    mcp_btn.click(fn=ask_via_mcp, outputs=mcp_output)

if __name__ == "__main__":
    demo.launch()
