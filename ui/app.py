"""
Continuum demo UI — live incident feed + recovery visualization.

Reads live from CockroachDB. Intended for the recorded demo video
(docs/DEMO_RUNBOOK.md) and the public Hugging Face Space, not production.
"""
import gradio as gr
import psycopg
from psycopg.rows import dict_row

from config import settings


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

if __name__ == "__main__":
    demo.launch()
