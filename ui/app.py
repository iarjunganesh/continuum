"""
Continuum demo UI — live incident-memory console.

A read-only NOC-style view straight into CockroachDB, built for the recorded
demo (submission/DEMO_SCRIPT.md) and the public Hugging Face Space. The centrepiece
is the **recovery timeline**: it makes the differentiating beat visible on
screen — a remediation step frozen in `executing` is exactly where the process
died, and the next cold invocation resumes there. State lives in CockroachDB,
not this process.

Read-only by construction: the main feed uses a direct psycopg connection, the
"via MCP" panel drives the same durable state through the CockroachDB Cloud
Managed MCP Server (read-only). Neither path ever writes — memory_agent.py
remains the only write path (CLAUDE.md, ADR 003).
"""

import asyncio
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr
import psycopg
from psycopg.rows import dict_row

# app_file is ui/app.py — a subdirectory. When Hugging Face (or `python ui/app.py`)
# runs this as a script, sys.path[0] is ui/, not the repo root, so `agents`/`config`
# won't import. Put the repo root on the path first, before those imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.query_agent import QueryAgent  # noqa: E402
from config import settings  # noqa: E402

query_agent = QueryAgent()

# UI polling cadence for the incident feed.
# Set CONTINUUM_UI_REFRESH_SECONDS=0 to disable auto-refresh entirely.
REFRESH_SECONDS = max(0.0, float(os.getenv("CONTINUUM_UI_REFRESH_SECONDS", "0")))
LOAD_ON_OPEN = os.getenv("CONTINUUM_UI_LOAD_ON_OPEN", "0") == "1"
REFRESH_LABEL = "manual refresh only" if REFRESH_SECONDS <= 0 else f"auto-refreshing every {REFRESH_SECONDS:g}s"

# ── Palette (dark ops surface; validated status colors from the dataviz skill).
# Status color never carries meaning alone — every chip ships an icon + label.
INK, INK2, MUTED = "#ffffff", "#c3c2b7", "#898781"
PLANE, SURF1, SURF2 = "#0d0d0d", "#161619", "#1e1e22"
BORDER = "rgba(255,255,255,0.10)"
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
NEUTRAL, PURPLE = "#3987e5", "#8b6dff"  # NEUTRAL = processing phase; PURPLE = brand

# Incident lifecycle → (color, glyph, label)
STATE_META = {
    "open": (WARNING, "◐", "Open"),
    "correlating": (NEUTRAL, "◍", "Correlating"),
    "remediating": (SERIOUS, "◉", "Remediating"),
    "resolved": (GOOD, "✓", "Resolved"),
    "escalated": (CRITICAL, "▲", "Escalated"),
}
SEVERITY_META = {
    "low": (NEUTRAL, "Low"),
    "medium": (WARNING, "Medium"),
    "high": (SERIOUS, "High"),
    "critical": (CRITICAL, "Critical"),
}
# How a step was reasoned about → (color, glyph, label). Read from
# remediation_steps.detail->>'reasoning_source'. Both Bedrock paths degrade
# silently by design, so a throttled account renders identically to a healthy
# one unless the timeline says which one ran. Steps written before this field
# existed have no value and simply render no chip.
SOURCE_META = {
    "bedrock": (PURPLE, "◆", "Claude via Bedrock"),
    "precedent_replay": (MUTED, "◇", "precedent replay (Bedrock unavailable)"),
    "no_precedent": (MUTED, "○", "no precedent — escalated"),
}
# Remediation step status → (color, glyph, label, pulse?)
STEP_META = {
    "proposed": (MUTED, "○", "proposed", False),
    "executing": (SERIOUS, "◐", "executing", True),  # the interruptible window
    "executed": (GOOD, "●", "executed", False),
    "failed": (CRITICAL, "✕", "failed", False),
    "skipped": (MUTED, "–", "skipped", False),
}

CSS = f"""
/* Override Gradio's theme tokens so native widgets (button, dropdown, code box)
   render dark on any Gradio version — belt to force-dark's suspenders. */
.gradio-container {{
  background: {PLANE} !important; max-width: 1180px !important;
  --body-background-fill: {PLANE}; --background-fill-primary: {SURF1};
  --background-fill-secondary: {SURF2}; --block-background-fill: {SURF1};
  --block-border-color: {BORDER}; --border-color-primary: {BORDER};
  --body-text-color: {INK}; --body-text-color-subdued: {MUTED};
  --button-primary-background-fill: linear-gradient(135deg, {PURPLE}, {NEUTRAL});
  --button-primary-background-fill-hover: linear-gradient(135deg, {NEUTRAL}, {PURPLE});
  --button-primary-text-color: #fff; --button-secondary-background-fill: {SURF2};
  --button-secondary-text-color: {INK}; --input-background-fill: {SURF1};
  --input-border-color: {BORDER}; --code-background-fill: {PLANE};
}}
footer {{ display: none !important; }}
.cx * {{ box-sizing: border-box; }}
.cx {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: {INK}; }}

/* Header */
.cx-hero {{
  border: 1px solid {BORDER}; border-radius: 16px; padding: 22px 24px;
  background:
    radial-gradient(120% 140% at 0% 0%, rgba(105,51,255,0.20), transparent 55%),
    radial-gradient(120% 140% at 100% 0%, rgba(57,135,229,0.16), transparent 55%),
    {SURF1};
}}
.cx-hero-top {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.cx-logo {{
  width: 34px; height: 34px; border-radius: 9px; flex: 0 0 auto;
  background: linear-gradient(135deg, {PURPLE}, {NEUTRAL});
  display: grid; place-items: center; font-size: 19px; font-weight: 700;
}}
.cx-title {{ font-size: 25px; font-weight: 700; letter-spacing: -0.02em; }}
.cx-sub {{ color: {INK2}; font-size: 14px; margin-top: 8px; max-width: 760px; line-height: 1.5; }}
.cx-pill {{
  margin-left: auto; display: inline-flex; align-items: center; gap: 7px;
  font-size: 12px; font-weight: 600; color: {INK2};
  border: 1px solid {BORDER}; border-radius: 999px; padding: 6px 12px; background: {PLANE};
}}
.cx-live {{ width: 8px; height: 8px; border-radius: 50%; background: {GOOD};
  box-shadow: 0 0 0 0 rgba(12,163,12,0.6); animation: cxpulse 2s infinite; }}
@keyframes cxpulse {{
  0% {{ box-shadow: 0 0 0 0 rgba(12,163,12,0.55); }}
  70% {{ box-shadow: 0 0 0 7px rgba(12,163,12,0); }}
  100% {{ box-shadow: 0 0 0 0 rgba(12,163,12,0); }}
}}

/* Resilience banner */
.cx-banner {{
  display: flex; gap: 14px; align-items: flex-start; margin-top: 14px;
  border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 18px; background: {SURF1};
}}
.cx-banner.hot {{ border-color: rgba(236,131,90,0.55);
  background: linear-gradient(90deg, rgba(236,131,90,0.16), {SURF1} 60%); }}
.cx-banner.cool {{ border-color: rgba(12,163,12,0.40);
  background: linear-gradient(90deg, rgba(12,163,12,0.12), {SURF1} 60%); }}
.cx-banner-ico {{ font-size: 22px; line-height: 1.1; }}
.cx-banner-t {{ font-weight: 700; font-size: 15px; }}
.cx-banner-d {{ color: {INK2}; font-size: 13px; margin-top: 4px; line-height: 1.5; }}

/* KPI tiles */
.cx-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 14px; }}
.cx-tile {{ border: 1px solid {BORDER}; border-radius: 14px; padding: 15px 16px; background: {SURF1};
  position: relative; overflow: hidden; }}
.cx-tile::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px; background: var(--accent); }}
.cx-tile-l {{ color: {MUTED}; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
.cx-tile-v {{ font-size: 30px; font-weight: 700; margin-top: 6px; letter-spacing: -0.02em; }}
.cx-tile-s {{ color: {INK2}; font-size: 12px; margin-top: 3px; }}

/* Section heading */
.cx-h {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
  color: {MUTED}; margin: 24px 2px 12px; }}

/* Incident cards */
.cx-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 13px; }}
.cx-card {{ border: 1px solid {BORDER}; border-radius: 14px; padding: 15px 16px; background: {SURF1};
  transition: border-color .15s, transform .15s; }}
.cx-card:hover {{ border-color: rgba(139,109,255,0.5); transform: translateY(-2px); }}
.cx-card-top {{ display: flex; align-items: center; gap: 8px; }}
.cx-svc {{ font-weight: 700; font-size: 15px; }}
.cx-meta {{ color: {MUTED}; font-size: 12px; margin: 7px 0 10px; }}
.cx-summary {{ color: {INK2}; font-size: 13px; line-height: 1.5; margin: 10px 0 12px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}

.cx-chip {{ display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; font-weight: 600;
  padding: 3px 9px; border-radius: 999px; border: 1px solid var(--c);
  color: var(--c); background: color-mix(in srgb, var(--c) 14%, transparent); }}
.cx-chip .g {{ font-size: 12px; }}

/* Mini stepper on cards */
.cx-mini {{ display: flex; align-items: center; gap: 0; margin-top: 4px; }}
.cx-dot {{ width: 13px; height: 13px; border-radius: 50%; flex: 0 0 auto;
  display: grid; place-items: center; font-size: 8px; color: {PLANE}; font-weight: 700;
  background: var(--c); border: 2px solid var(--c); }}
.cx-dot.hollow {{ background: transparent; color: var(--c); }}
.cx-seg {{ height: 2px; flex: 1 1 auto; background: {BORDER}; min-width: 8px; }}
.cx-mini-lbl {{ color: {MUTED}; font-size: 12px; margin-left: 10px; white-space: nowrap; }}
.cx-pulse {{ animation: cxdot 1.3s ease-in-out infinite; }}
@keyframes cxdot {{ 0%,100% {{ box-shadow: 0 0 0 0 rgba(236,131,90,0.55); }}
  50% {{ box-shadow: 0 0 0 5px rgba(236,131,90,0); }} }}

/* Recovery timeline (drill-down) */
.cx-tl {{ border: 1px solid {BORDER}; border-radius: 14px; padding: 18px 20px; background: {SURF1}; }}
.cx-tl-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding-bottom: 14px; margin-bottom: 6px; border-bottom: 1px solid {BORDER}; }}
.cx-tl-svc {{ font-weight: 700; font-size: 16px; }}
.cx-row {{ display: grid; grid-template-columns: 26px 1fr; gap: 14px; }}
.cx-rail {{ display: flex; flex-direction: column; align-items: center; }}
.cx-node {{ width: 22px; height: 22px; border-radius: 50%; flex: 0 0 auto; display: grid;
  place-items: center; font-size: 11px; font-weight: 700; color: {PLANE};
  background: var(--c); border: 2px solid var(--c); z-index: 1; }}
.cx-node.hollow {{ background: {SURF1}; color: var(--c); }}
.cx-line {{ width: 2px; flex: 1 1 auto; background: {BORDER}; min-height: 18px; }}
.cx-line.done {{ background: {GOOD}; }}
.cx-body {{ padding-bottom: 20px; }}
.cx-body-t {{ display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }}
.cx-idx {{ color: {MUTED}; font-size: 12px; font-variant-numeric: tabular-nums; }}
.cx-action {{ font-weight: 600; font-size: 14px; }}
.cx-flag {{ display: inline-flex; align-items: center; gap: 6px; margin-top: 8px;
  font-size: 12.5px; font-weight: 600; color: {SERIOUS};
  border: 1px dashed rgba(236,131,90,0.6); border-radius: 8px; padding: 5px 10px;
  background: rgba(236,131,90,0.10); }}
/* Recalled precedent — what the vector search actually returned for a step.
   Purple-tinted to read as "this came from semantic memory", distinct from the
   orange interruption flag which reads as "this is where it died". */
.cx-prec {{ margin-top: 9px; border-left: 2px solid rgba(139,109,255,0.55); border-radius: 0 8px 8px 0;
  padding: 8px 12px; background: rgba(139,109,255,0.08); }}
.cx-prec-h {{ display: flex; align-items: center; gap: 9px; flex-wrap: wrap;
  font-size: 11.5px; font-weight: 700; color: {PURPLE}; text-transform: uppercase; letter-spacing: 0.04em; }}
.cx-dist {{ font-variant-numeric: tabular-nums; color: {INK2}; font-weight: 600;
  text-transform: none; letter-spacing: 0; }}
.cx-pid {{ color: {MUTED}; font-weight: 500; text-transform: none; letter-spacing: 0;
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }}
.cx-prec-s {{ color: {INK2}; font-size: 12.5px; line-height: 1.5; margin-top: 5px; font-style: italic; }}
.cx-when {{ color: {MUTED}; font-size: 12px; margin-top: 5px; }}

/* Resilience evidence — static, read from the committed run rather than the
   cluster, so this section costs zero Request Units to render. */
.cx-eviz {{ color: {INK2}; font-size: 13px; line-height: 1.6; margin: 14px 2px 4px; }}
.cx-figs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; margin-top: 12px; }}
.cx-fig {{ margin: 0; border: 1px solid {BORDER}; border-radius: 14px; overflow: hidden; background: {PLANE}; }}
.cx-fig svg {{ display: block; width: 100%; height: auto; }}
.cx-figcap {{ color: {MUTED}; font-size: 12px; padding: 9px 14px 12px; border-top: 1px solid {BORDER}; }}

.cx-empty {{ border: 1px dashed {BORDER}; border-radius: 14px; padding: 34px; text-align: center;
  color: {INK2}; background: {SURF1}; }}
.cx-foot {{ color: {MUTED}; font-size: 12px; text-align: center; margin: 22px 0 6px; }}
"""


# ── Rendering helpers ────────────────────────────────────────────────────────
def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def _ago(dt) -> str:
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 60:
        return "just now"
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= size:
            return f"{int(secs // size)}{unit} ago"
    return "just now"


def _chip(color: str, glyph: str, label: str) -> str:
    return f'<span class="cx-chip" style="--c:{color}"><span class="g">{glyph}</span>{_esc(label)}</span>'


def _source_chip(source: str | None) -> str:
    """Chip naming the reasoning path behind a step. Empty for steps written
    before the field existed — absence is not evidence of a fallback."""
    if not source or source not in SOURCE_META:
        return ""
    return _chip(*SOURCE_META[source])


def _precedent_block(step: dict) -> str:
    """Render what semantic memory actually recalled for this step.

    The pipeline always ran, but its *result* used to be invisible: the UI
    showed that Bedrock had reasoned, never which past incident it reasoned
    from. Showing the matched summary and its vector distance is what turns
    "Distributed Vector Indexing" from a claim in the README into something a
    judge can watch happen. Steps with no precedent — or written before these
    fields existed — render nothing rather than an empty shell.
    """
    summary = step.get("precedent_summary")
    if not summary:
        return ""
    distance = step.get("precedent_distance")
    considered = step.get("precedents_considered")
    pid = step.get("precedent_id") or ""
    bits = []
    if distance is not None:
        # L2 distance from the C-SPANN search (`<->`, not `<=>` cosine — the
        # schema and correlation_agent both use L2, so it is unbounded above
        # rather than 0–2). Smaller is closer; shown to 4 dp because the range
        # between a strong and a weak match lives in the lower decimals.
        bits.append(f'<span class="cx-dist">distance {_esc(f"{float(distance):.4f}")}</span>')
    if pid:
        bits.append(f'<span class="cx-pid">incident {_esc(pid[:8])}</span>')
    if considered:
        bits.append(f'<span class="cx-pid">{_esc(considered)} candidates ranked</span>')
    return f"""
        <div class="cx-prec">
          <div class="cx-prec-h">◆ recalled from memory {"".join(bits)}</div>
          <div class="cx-prec-s">“{_esc(summary)}”</div>
        </div>"""


def _mini_stepper(steps: list[dict]) -> str:
    if not steps:
        return '<div class="cx-mini-lbl">no steps yet</div>'
    parts = ['<div class="cx-mini">']
    for i, s in enumerate(steps):
        color, glyph, _, pulse = STEP_META.get(s["status"], (MUTED, "○", "?", False))
        hollow = " hollow" if s["status"] in ("proposed", "skipped") else ""
        pcls = " cx-pulse" if pulse else ""
        parts.append(f'<span class="cx-dot{hollow}{pcls}" style="--c:{color}">{glyph}</span>')
        if i < len(steps) - 1:
            done = "done" if s["status"] == "executed" else ""
            parts.append(f'<span class="cx-seg {done}"></span>')
    done_n = sum(1 for s in steps if s["status"] == "executed")
    parts.append("</div>")
    parts.append(f'<span class="cx-mini-lbl">{done_n}/{len(steps)} steps executed</span>')
    return "".join(parts)


def _incident_card(row: dict, steps: list[dict]) -> str:
    s_color, s_glyph, s_label = STATE_META.get(row["state"], (MUTED, "○", row["state"]))
    v_color, v_label = SEVERITY_META.get(row["severity"], (MUTED, row["severity"]))
    summary = _esc(row.get("summary") or "No summary recorded.")
    return f"""
    <div class="cx-card">
      <div class="cx-card-top">
        <span class="cx-svc">{_esc(row["service"])}</span>
        <span style="margin-left:auto">{_chip(v_color, "●", v_label)}</span>
      </div>
      <div class="cx-meta">{_esc(row["region"])} · opened {_ago(row.get("opened_at"))}
        · <span style="font-family:monospace">{_esc(str(row["incident_id"])[:8])}</span></div>
      <div>{_chip(s_color, s_glyph, s_label)}</div>
      <div class="cx-summary">{summary}</div>
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px">{_mini_stepper(steps)}</div>
    </div>"""


def _stat_tile(label: str, value, accent: str, sub: str) -> str:
    return (
        f'<div class="cx-tile" style="--accent:{accent}">'
        f'<div class="cx-tile-l">{label}</div>'
        f'<div class="cx-tile-v">{value}</div>'
        f'<div class="cx-tile-s">{sub}</div></div>'
    )


def _banner(executing: int, open_n: int) -> str:
    if executing > 0:
        plural = "step" if executing == 1 else "steps"
        return f"""
        <div class="cx-banner hot">
          <div class="cx-banner-ico">⏸</div>
          <div>
            <div class="cx-banner-t">{executing} remediation {plural} in-flight (status =
              <span style="color:{SERIOUS}">executing</span>)</div>
            <div class="cx-banner-d">This state is committed to CockroachDB <em>before</em> execution
              begins. Kill the orchestrator now (<code>scripts/chaos_kill.py</code>) and the next cold
              invocation reads this exact step back and resumes it — no restart from scratch, no lost
              context. The process is disposable; the memory isn't.</div>
          </div>
        </div>"""
    return f"""
    <div class="cx-banner cool">
      <div class="cx-banner-ico">✓</div>
      <div>
        <div class="cx-banner-t">No steps in-flight — {open_n} open incident(s) fully checkpointed</div>
        <div class="cx-banner-d">Every executed step is durably committed in CockroachDB. Recovery from a
          process kill is a single cold read away; nothing here depends on warm process memory (ADR 002).</div>
      </div>
    </div>"""


# ── Data access (read-only) ──────────────────────────────────────────────────
def _connect():
    return psycopg.connect(settings.cockroach_database_url)


def load_dashboard():
    """Returns (banner_html, kpis_html, cards_html, dropdown_update)."""
    try:
        with _connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT i.incident_id, i.service, i.region, i.severity, i.state,
                       i.summary, i.opened_at, i.updated_at,
                       count(s.step_id) FILTER (WHERE s.status = 'executed')  AS steps_executed,
                       count(s.step_id) FILTER (WHERE s.status = 'executing') AS steps_executing
                FROM incidents i
                LEFT JOIN remediation_steps s ON s.incident_id = i.incident_id
                GROUP BY i.incident_id, i.service, i.region, i.severity, i.state,
                         i.summary, i.opened_at, i.updated_at
                ORDER BY i.updated_at DESC
                LIMIT 24
            """)
            incidents = cur.fetchall()

            cur.execute("""
                SELECT incident_id, step_index, action, status, created_at
                FROM remediation_steps
                WHERE incident_id IN (
                    SELECT incident_id FROM incidents ORDER BY updated_at DESC LIMIT 24
                )
                ORDER BY incident_id, step_index
            """)
            steps_by_incident: dict = {}
            for s in cur.fetchall():
                steps_by_incident.setdefault(str(s["incident_id"]), []).append(s)
    except Exception as exc:  # no DB / bad URL — keep the Space alive with a clear message
        empty = (
            f'<div class="cx-empty"><b>Waiting on CockroachDB.</b><br>'
            f"Set <code>COCKROACH_DATABASE_URL</code> as a Space secret to bring the feed live.<br>"
            f'<span style="color:{MUTED};font-size:12px">{_esc(exc)}</span></div>'
        )
        return empty, "", empty, gr.update(choices=[], value=None)

    open_states = {"open", "correlating", "remediating"}
    open_n = sum(1 for r in incidents if r["state"] in open_states)
    resolved_n = sum(1 for r in incidents if r["state"] == "resolved")
    executing_n = sum(int(r["steps_executing"]) for r in incidents)
    executed_n = sum(int(r["steps_executed"]) for r in incidents)

    kpis = "".join(
        [
            _stat_tile("Open incidents", open_n, WARNING, "correlating · remediating"),
            _stat_tile("In-flight now", executing_n, SERIOUS, "steps mid-execution"),
            _stat_tile("Resolved", resolved_n, GOOD, "closed by the agent"),
            _stat_tile("Steps committed", executed_n, NEUTRAL, "durable in CockroachDB"),
        ]
    )
    kpis = f'<div class="cx-kpis">{kpis}</div>'

    if incidents:
        cards = "".join(_incident_card(r, steps_by_incident.get(str(r["incident_id"]), [])) for r in incidents)
        cards = f'<div class="cx-grid">{cards}</div>'
    else:
        cards = (
            '<div class="cx-empty"><b>No incidents yet.</b><br>'
            "Run <code>make seed-data</code> or fire the synthetic alert stream to populate memory.</div>"
        )

    choices = [
        (
            f"{r['service']} · {STATE_META.get(r['state'], ('', '', r['state']))[2]} · {str(r['incident_id'])[:8]}",
            str(r["incident_id"]),
        )
        for r in incidents
    ]
    return _banner(executing_n, open_n), kpis, cards, gr.update(choices=choices)


def load_timeline(incident_id: str | None):
    if not incident_id:
        return (
            '<div class="cx-empty">Pick an incident above to replay its remediation log — '
            "the same append-only history a recovering invocation reads back on a cold start.</div>"
        )
    try:
        with _connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT service, region, severity, state, summary, opened_at
                FROM incidents WHERE incident_id = %s
            """,
                (incident_id,),
            )
            head = cur.fetchone()
            cur.execute(
                """
                SELECT step_index, action, status, proposed_by, created_at,
                       detail ->> 'reasoning_source'   AS reasoning_source,
                       detail ->> 'based_on'           AS precedent_id,
                       detail ->> 'precedent_summary'  AS precedent_summary,
                       detail ->> 'precedent_distance' AS precedent_distance,
                       detail ->> 'precedents_considered' AS precedents_considered
                FROM remediation_steps WHERE incident_id = %s ORDER BY step_index
            """,
                (incident_id,),
            )
            steps = cur.fetchall()
    except Exception as exc:
        return f'<div class="cx-empty">Timeline query failed: {_esc(exc)}</div>'

    if not head:
        return '<div class="cx-empty">Incident not found.</div>'

    s_color, s_glyph, s_label = STATE_META.get(head["state"], (MUTED, "○", head["state"]))
    v_color, v_label = SEVERITY_META.get(head["severity"], (MUTED, head["severity"]))
    rows = []
    for i, s in enumerate(steps):
        color, glyph, label, pulse = STEP_META.get(s["status"], (MUTED, "○", s["status"], False))
        hollow = " hollow" if s["status"] in ("proposed", "skipped") else ""
        pcls = " cx-pulse" if pulse else ""
        line = (
            ""
            if i == len(steps) - 1
            else (
                '<span class="cx-line done"></span>' if s["status"] == "executed" else '<span class="cx-line"></span>'
            )
        )
        flag = (
            (
                '<div class="cx-flag">◀ the process died here — the next cold invocation '
                "resumes at exactly this step</div>"
            )
            if pulse
            else ""
        )
        rows.append(f"""
        <div class="cx-row">
          <div class="cx-rail">
            <span class="cx-node{hollow}{pcls}" style="--c:{color}">{glyph}</span>{line}
          </div>
          <div class="cx-body">
            <div class="cx-body-t">
              <span class="cx-idx">step {s["step_index"]}</span>
              <span class="cx-action">{_esc(s["action"])}</span>
              {_chip(color, glyph, label)}
              {_source_chip(s.get("reasoning_source"))}
            </div>
            {flag}
            {_precedent_block(s)}
            <div class="cx-when">{_ago(s.get("created_at"))} · {_esc(s.get("proposed_by"))}</div>
          </div>
        </div>""")
    if not rows:
        rows.append('<div class="cx-empty">No remediation steps logged for this incident yet.</div>')

    return f"""
    <div class="cx-tl">
      <div class="cx-tl-head">
        <span class="cx-tl-svc">{_esc(head["service"])}</span>
        {_chip(v_color, "●", v_label)}
        {_chip(s_color, s_glyph, s_label)}
        <span style="color:{MUTED};font-size:12px;margin-left:auto">{_esc(head["region"])}
          · opened {_ago(head.get("opened_at"))}</span>
      </div>
      <div style="color:{INK2};font-size:13px;margin:2px 0 16px">{_esc(head.get("summary") or "")}</div>
      {"".join(rows)}
    </div>"""


def _leaf_errors(exc: BaseException) -> str:
    """The MCP client raises from inside an anyio TaskGroup, so str(exc) is
    the useless 'unhandled errors in a TaskGroup (1 sub-exception)' — unwrap
    ExceptionGroups recursively and report the actual leaf errors instead."""
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(_leaf_errors(e) for e in exc.exceptions)
    return f"{type(exc).__name__}: {exc}"


def ask_via_mcp():
    """Same durable state, driven through the CockroachDB Cloud Managed MCP
    Server (read-only) rather than a direct connection — demonstrates the app
    itself calling MCP at runtime (ADR 003), not just Claude Code in dev."""
    if not settings.cockroach_mcp_api_key or not settings.cockroach_mcp_cluster_id:
        return (
            "MCP not configured: set COCKROACH_MCP_API_KEY and COCKROACH_MCP_CLUSTER_ID "
            "as Space secrets. Key: CockroachDB Cloud console → Access Management → "
            "Service Accounts (Cluster Operator role on this cluster); cluster id: the "
            "UUID in the console URL. See .env.example."
        )
    try:
        result = asyncio.run(query_agent.list_open_incidents())
    except Exception as exc:
        return f"MCP query failed: {_leaf_errors(exc)}"
    return json.dumps(result.rows, indent=2, default=str)


# ── Resilience evidence ───────────────────────────────────────────────────────
# The console answers "what is happening right now"; this section answers "how
# often is it wrong when things go badly", which is the actual claim. Read from
# the newest committed evidence run rather than the cluster: these are results
# of past forced failures, so re-deriving them live would cost Request Units to
# recompute numbers that are already durable — and would quietly turn a stated
# result into whatever today's run happened to produce.
#
# Every figure below is computed from the run's JSON. Nothing is hardcoded: a
# number typed into this file would be a fifth place for the benchmarks to drift
# out of sync with themselves, which is exactly what check_drift.py exists to
# stop. If the folder is missing the section degrades to an honest note.
REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "assets" / "resilience-run"
CHARTS_DIR = REPO_ROOT / "assets" / "charts"

# SVG only, deliberately. The Space sync workflow strips binaries before pushing
# to the Hub (Xet/LFS is required for them over plain git), so a PNG here would
# render as a broken image on the public demo while looking fine locally.
_CHARTS = [
    ("chart-kill-storm-dark.svg", "Fifty kills, fifty resumes"),
    ("chart-lambda-timeout-dark.svg", "AWS performs the kill"),
    ("chart-throughput-dark.svg", "Concurrency absorbed, not rejected"),
    ("chart-vector-scale-dark.svg", "C-SPANN against a forced full scan"),
]


def _newest_run() -> Path | None:
    runs = [p for p in RUNS_DIR.glob("*/evidence") if p.is_dir()]
    return max(runs, key=lambda p: p.stat().st_mtime).parent if runs else None


def _load_evidence(run: Path) -> dict:
    """Load a run's suite JSONs, keyed by suite name. Missing files are skipped
    so a partial run still renders what it does have."""
    out = {}
    for path in (run / "evidence").glob("*.json"):
        suite = path.stem.split("_", 1)[-1]
        try:
            out[suite] = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
    return out


def _evidence_tiles(data: dict) -> list[str]:
    """Headline correctness figures.

    Correctness counts are absolute, not percentiles: any non-zero duplicate or
    lost step is a defect, so they are shown as raw counts. A "99.9% exactly
    once" would be a failure wearing a percentage.
    """
    tiles = []
    storm = data.get("kill-storm")
    if storm:
        tiles.append(
            _stat_tile(
                "Kill storm",
                f"{storm['resumed']}/{storm['n']}",
                GOOD,
                f"{storm['duplicated']} duplicated · {storm['lost']} lost · {storm['wrong_step']} wrong step",
            )
        )
    sigkill = data.get("real-sigkill")
    if sigkill:
        tiles.append(
            _stat_tile(
                "Real SIGKILL",
                f"{sigkill['survived']}/{sigkill['n']}",
                GOOD,
                f"genuine process kills · {sigkill['duplicated']} duplicated",
            )
        )
    lam = data.get("lambda-timeout")
    if lam:
        tiles.append(
            _stat_tile(
                "AWS Lambda timeout",
                f"{lam['resumed']}/{lam['n']}",
                PURPLE,
                f"{lam['timed_out']} killed by AWS, no catchable signal",
            )
        )
    once = data.get("exactly-once")
    if once:
        trials = sum(r["trials"] for r in once)
        violations = sum(r["violations"] for r in once)
        peak = max(r["concurrency"] for r in once)
        tiles.append(
            _stat_tile(
                "Exactly-once",
                f"{violations} violations",
                GOOD if violations == 0 else CRITICAL,
                f"{trials} trials, up to {peak}-way contention",
            )
        )
    return tiles


def _evidence_note(data: dict) -> str:
    """One line of context drawn from the numbers themselves."""
    bits = []
    tp = data.get("agent-throughput")
    if tp:
        best = max(tp, key=lambda r: r["throughput"])
        bits.append(
            f"{best['agents']} concurrent agents sustained {best['throughput']:.1f} completed/s "
            f"with {sum(r['failures'] for r in tp)} failures"
        )
    vs = data.get("vector-scale")
    if vs:
        biggest = max(vs, key=lambda r: r["vectors"])
        speedup = biggest["brute_warm_p50"] / biggest["ann_warm_p50"]
        bits.append(
            f"C-SPANN {speedup:.1f}× faster than a full scan at {biggest['vectors']:,} vectors "
            f"({biggest['ann_warm_p50']:.0f} ms vs {biggest['brute_warm_p50']:.0f} ms, warm)"
        )
    return " · ".join(bits)


def load_evidence() -> str:
    run = _newest_run()
    if run is None:
        return (
            '<div class="cx"><div class="cx-empty">No evidence run committed yet — '
            "run <code>make resilience-bench</code> to generate one.</div></div>"
        )
    data = _load_evidence(run)
    tiles = _evidence_tiles(data)
    if not tiles:
        return (
            f'<div class="cx"><div class="cx-empty">Evidence run {_esc(run.name)} has no readable suites.</div></div>'
        )

    charts = []
    for filename, caption in _CHARTS:
        path = CHARTS_DIR / filename
        if not path.exists():
            continue
        # Inlined rather than <img src=...>: Gradio serves only allowed paths
        # and the Space's file routing differs from local, so an inline <svg>
        # is the one form that renders identically in both.
        charts.append(
            f'<figure class="cx-fig">{path.read_text(encoding="utf-8")}'
            f'<figcaption class="cx-figcap">{_esc(caption)}</figcaption></figure>'
        )

    note = _evidence_note(data)
    return f"""
    <div class="cx">
      <div class="cx-kpis">{"".join(tiles)}</div>
      <div class="cx-eviz">{note}</div>
      <div class="cx-figs">{"".join(charts)}</div>
      <div class="cx-when" style="margin-top:10px">Evidence run <code>{_esc(run.name)}</code> ·
        committed under <code>assets/resilience-run/</code> with the git commit that produced it ·
        charts regenerated by <code>make charts</code>, never screenshotted</div>
    </div>"""


# ── Force dark so the recorded demo always reads as an ops console ────────────
_FORCE_DARK = """
() => {
  const u = new URL(window.location);
  if (u.searchParams.get('__theme') !== 'dark') {
    u.searchParams.set('__theme', 'dark');
    window.location.replace(u.href);
  }
}
"""

_HERO = """
<div class="cx">
  <div class="cx-hero">
    <div class="cx-hero-top">
      <div class="cx-logo">↻</div>
      <div class="cx-title">Continuum</div>
      <span class="cx-pill"><span class="cx-live"></span>LIVE · CockroachDB · eu-central-1</span>
    </div>
    <div class="cx-sub">An autonomous incident-response agent that resumes the exact step it was
      killed on — because its memory lives in CockroachDB, not its own process. Every panel below
      reads live from CockroachDB. Kill the orchestrator mid-remediation and the step it died on
      stays <code>executing</code> — the next cold invocation resumes exactly there.
      <b>State persists; the process doesn't.</b></div>
  </div>
</div>
"""

theme = gr.themes.Base(
    primary_hue=gr.themes.colors.purple,
    neutral_hue=gr.themes.colors.slate,
    font=["system-ui", "-apple-system", "Segoe UI", "sans-serif"],
)

with gr.Blocks(title="Continuum — Live Incident Memory", analytics_enabled=False) as demo:
    # analytics_enabled=False: Gradio's launch-time telemetry compares this
    # theme's font list against built-in themes' Font objects; Font.__eq__
    # doesn't guard against comparing to a plain str, so a custom string font
    # list crashes with AttributeError('str' object has no attribute 'name')
    # whenever analytics is on (the Spaces default). Disabling it sidesteps
    # the crash and means this read-only demo doesn't phone home either way.
    # Inject the stylesheet as a <style> block rather than via the css= param:
    # css/theme/js moved from Blocks() to launch() in Gradio 6.0, so a <style>
    # component is the one delivery that renders identically on 5.x and 6.x.
    gr.HTML(f"<style>{CSS}</style>")
    gr.HTML(_HERO)
    banner = gr.HTML()
    kpis = gr.HTML()

    with gr.Row():
        refresh_btn = gr.Button("↻ Refresh now", variant="primary", scale=0)
        gr.HTML(f'<div class="cx" style="color:#898781;font-size:12px;align-self:center">{_esc(REFRESH_LABEL)}</div>')

    gr.HTML('<div class="cx"><div class="cx-h">Incident memory · live from CockroachDB</div></div>')
    cards = gr.HTML()

    gr.HTML('<div class="cx"><div class="cx-h">Recovery timeline · replay a remediation log</div></div>')
    incident_dd = gr.Dropdown(label="Incident", choices=[], interactive=True, filterable=True)
    timeline = gr.HTML(load_timeline(None))

    # Static and load-time: these are results of past forced failures, so there
    # is nothing to refresh and no Request Unit to spend.
    gr.HTML('<div class="cx"><div class="cx-h">Proven under failure · committed evidence, not claims</div></div>')
    gr.HTML(load_evidence())

    gr.HTML('<div class="cx"><div class="cx-h">Same state, over the Managed MCP Server (read-only)</div></div>')
    with gr.Row():
        mcp_btn = gr.Button("Ask via MCP: what's open right now?", scale=0)
    mcp_output = gr.Code(label="Open incidents — answered over the MCP protocol", language="json")

    gr.HTML(
        '<div class="cx"><div class="cx-foot">Continuum · CockroachDB × AWS Hackathon 2026 · '
        "read-only view · memory lives in CockroachDB, not this process</div></div>"
    )

    # Wiring — manual-first by default to minimize CockroachDB RU consumption.
    dash_outputs = [banner, kpis, cards, incident_dd]
    if LOAD_ON_OPEN:
        demo.load(fn=load_dashboard, outputs=dash_outputs)
    refresh_btn.click(fn=load_dashboard, outputs=dash_outputs)
    if REFRESH_SECONDS > 0:
        gr.Timer(REFRESH_SECONDS).tick(fn=load_dashboard, outputs=[banner, kpis, cards])  # not the dropdown
    incident_dd.change(fn=load_timeline, inputs=incident_dd, outputs=timeline)
    mcp_btn.click(fn=ask_via_mcp, outputs=mcp_output)

if __name__ == "__main__":
    # theme + js live on launch() in Gradio 6.x but on Blocks() in 5.x — pass
    # them only if this launch() accepts them, so the app never crashes on a
    # version mismatch. The <style> block + token overrides above already carry
    # the dark look; theme/js are enhancements (accent hue + force-dark).
    import inspect

    _accepted = inspect.signature(demo.launch).parameters
    _kwargs = {}
    if "theme" in _accepted:
        _kwargs["theme"] = theme
    if "js" in _accepted:
        _kwargs["js"] = _FORCE_DARK
    demo.launch(**_kwargs)
