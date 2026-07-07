"""
Continuum demo UI — live incident-memory console.

A read-only NOC-style view straight into CockroachDB, built for the recorded
demo (docs/DEMO_RUNBOOK.md) and the public Hugging Face Space. The centrepiece
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

# ── Palette (dark ops surface; validated status colors from the dataviz skill).
# Status color never carries meaning alone — every chip ships an icon + label.
INK, INK2, MUTED = "#ffffff", "#c3c2b7", "#898781"
PLANE, SURF1, SURF2 = "#0d0d0d", "#161619", "#1e1e22"
BORDER = "rgba(255,255,255,0.10)"
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
NEUTRAL, PURPLE = "#3987e5", "#8b6dff"  # NEUTRAL = processing phase; PURPLE = brand

# Incident lifecycle → (color, glyph, label)
STATE_META = {
    "open":        (WARNING,  "◐", "Open"),
    "correlating": (NEUTRAL,  "◍", "Correlating"),
    "remediating": (SERIOUS,  "◉", "Remediating"),
    "resolved":    (GOOD,     "✓", "Resolved"),
    "escalated":   (CRITICAL, "▲", "Escalated"),
}
SEVERITY_META = {
    "low":      (NEUTRAL,  "Low"),
    "medium":   (WARNING,  "Medium"),
    "high":     (SERIOUS,  "High"),
    "critical": (CRITICAL, "Critical"),
}
# Remediation step status → (color, glyph, label, pulse?)
STEP_META = {
    "proposed":  (MUTED,    "○", "proposed",  False),
    "executing": (SERIOUS,  "◐", "executing", True),   # the interruptible window
    "executed":  (GOOD,     "●", "executed",  False),
    "failed":    (CRITICAL, "✕", "failed",    False),
    "skipped":   (MUTED,    "–", "skipped",   False),
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
.cx-when {{ color: {MUTED}; font-size: 12px; margin-top: 5px; }}

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
    return (f'<span class="cx-chip" style="--c:{color}">'
            f'<span class="g">{glyph}</span>{_esc(label)}</span>')


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
    parts.append('</div>')
    parts.append(f'<span class="cx-mini-lbl">{done_n}/{len(steps)} steps executed</span>')
    return "".join(parts)


def _incident_card(row: dict, steps: list[dict]) -> str:
    s_color, s_glyph, s_label = STATE_META.get(row["state"], (MUTED, "○", row["state"]))
    v_color, v_label = SEVERITY_META.get(row["severity"], (MUTED, row["severity"]))
    summary = _esc(row.get("summary") or "No summary recorded.")
    return f"""
    <div class="cx-card">
      <div class="cx-card-top">
        <span class="cx-svc">{_esc(row['service'])}</span>
        <span style="margin-left:auto">{_chip(v_color, '●', v_label)}</span>
      </div>
      <div class="cx-meta">{_esc(row['region'])} · opened {_ago(row.get('opened_at'))}
        · <span style="font-family:monospace">{_esc(str(row['incident_id'])[:8])}</span></div>
      <div>{_chip(s_color, s_glyph, s_label)}</div>
      <div class="cx-summary">{summary}</div>
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px">{_mini_stepper(steps)}</div>
    </div>"""


def _stat_tile(label: str, value, accent: str, sub: str) -> str:
    return (f'<div class="cx-tile" style="--accent:{accent}">'
            f'<div class="cx-tile-l">{label}</div>'
            f'<div class="cx-tile-v">{value}</div>'
            f'<div class="cx-tile-s">{sub}</div></div>')


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
        empty = (f'<div class="cx-empty"><b>Waiting on CockroachDB.</b><br>'
                 f'Set <code>COCKROACH_DATABASE_URL</code> as a Space secret to bring the feed live.<br>'
                 f'<span style="color:{MUTED};font-size:12px">{_esc(exc)}</span></div>')
        return empty, "", empty, gr.update(choices=[], value=None)

    open_states = {"open", "correlating", "remediating"}
    open_n = sum(1 for r in incidents if r["state"] in open_states)
    resolved_n = sum(1 for r in incidents if r["state"] == "resolved")
    executing_n = sum(int(r["steps_executing"]) for r in incidents)
    executed_n = sum(int(r["steps_executed"]) for r in incidents)

    kpis = "".join([
        _stat_tile("Open incidents", open_n, WARNING, "correlating · remediating"),
        _stat_tile("In-flight now", executing_n, SERIOUS, "steps mid-execution"),
        _stat_tile("Resolved", resolved_n, GOOD, "closed by the agent"),
        _stat_tile("Steps committed", executed_n, NEUTRAL, "durable in CockroachDB"),
    ])
    kpis = f'<div class="cx-kpis">{kpis}</div>'

    if incidents:
        cards = "".join(
            _incident_card(r, steps_by_incident.get(str(r["incident_id"]), []))
            for r in incidents
        )
        cards = f'<div class="cx-grid">{cards}</div>'
    else:
        cards = ('<div class="cx-empty"><b>No incidents yet.</b><br>'
                 'Run <code>make seed-data</code> or fire the synthetic alert stream to populate memory.</div>')

    choices = [
        (f"{r['service']} · {STATE_META.get(r['state'], ('', '', r['state']))[2]} · "
         f"{str(r['incident_id'])[:8]}", str(r["incident_id"]))
        for r in incidents
    ]
    return _banner(executing_n, open_n), kpis, cards, gr.update(choices=choices)


def load_timeline(incident_id: str | None):
    if not incident_id:
        return ('<div class="cx-empty">Pick an incident above to replay its remediation log — '
                'the same append-only history a recovering invocation reads back on a cold start.</div>')
    try:
        with _connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT service, region, severity, state, summary, opened_at
                FROM incidents WHERE incident_id = %s
            """, (incident_id,))
            head = cur.fetchone()
            cur.execute("""
                SELECT step_index, action, status, proposed_by, created_at
                FROM remediation_steps WHERE incident_id = %s ORDER BY step_index
            """, (incident_id,))
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
        line = "" if i == len(steps) - 1 else (
            '<span class="cx-line done"></span>' if s["status"] == "executed"
            else '<span class="cx-line"></span>')
        flag = ('<div class="cx-flag">◀ the process died here — the next cold invocation '
                'resumes at exactly this step</div>') if pulse else ""
        rows.append(f"""
        <div class="cx-row">
          <div class="cx-rail">
            <span class="cx-node{hollow}{pcls}" style="--c:{color}">{glyph}</span>{line}
          </div>
          <div class="cx-body">
            <div class="cx-body-t">
              <span class="cx-idx">step {s['step_index']}</span>
              <span class="cx-action">{_esc(s['action'])}</span>
              {_chip(color, glyph, label)}
            </div>
            {flag}
            <div class="cx-when">{_ago(s.get('created_at'))} · {_esc(s.get('proposed_by'))}</div>
          </div>
        </div>""")
    if not rows:
        rows.append('<div class="cx-empty">No remediation steps logged for this incident yet.</div>')

    return f"""
    <div class="cx-tl">
      <div class="cx-tl-head">
        <span class="cx-tl-svc">{_esc(head['service'])}</span>
        {_chip(v_color, '●', v_label)}
        {_chip(s_color, s_glyph, s_label)}
        <span style="color:{MUTED};font-size:12px;margin-left:auto">{_esc(head['region'])}
          · opened {_ago(head.get('opened_at'))}</span>
      </div>
      <div style="color:{INK2};font-size:13px;margin:2px 0 16px">{_esc(head.get('summary') or '')}</div>
      {''.join(rows)}
    </div>"""


def ask_via_mcp():
    """Same durable state, driven through the CockroachDB Cloud Managed MCP
    Server (read-only) rather than a direct connection — demonstrates the app
    itself calling MCP at runtime (ADR 003), not just Claude Code in dev."""
    try:
        result = asyncio.run(query_agent.list_open_incidents())
    except Exception as exc:
        return f"MCP query failed (endpoint/key not configured?): {exc}"
    return json.dumps(result.rows, indent=2, default=str)


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
        gr.HTML('<div class="cx" style="color:#898781;font-size:12px;align-self:center">'
                'auto-refreshing every 5s</div>')

    gr.HTML('<div class="cx"><div class="cx-h">Incident memory · live from CockroachDB</div></div>')
    cards = gr.HTML()

    gr.HTML('<div class="cx"><div class="cx-h">Recovery timeline · replay a remediation log</div></div>')
    incident_dd = gr.Dropdown(label="Incident", choices=[], interactive=True, filterable=True)
    timeline = gr.HTML(load_timeline(None))

    gr.HTML('<div class="cx"><div class="cx-h">Same state, over the Managed MCP Server (read-only)</div></div>')
    with gr.Row():
        mcp_btn = gr.Button("Ask via MCP: what's open right now?", scale=0)
    mcp_output = gr.Code(label="Open incidents — answered over the MCP protocol", language="json")

    gr.HTML('<div class="cx"><div class="cx-foot">Continuum · CockroachDB × AWS Hackathon 2026 · '
            'read-only view · memory lives in CockroachDB, not this process</div></div>')

    # Wiring — the timer keeps the feed alive without touching the drill-down selection.
    dash_outputs = [banner, kpis, cards, incident_dd]
    demo.load(fn=load_dashboard, outputs=dash_outputs)
    refresh_btn.click(fn=load_dashboard, outputs=dash_outputs)
    gr.Timer(5.0).tick(fn=load_dashboard, outputs=[banner, kpis, cards])  # not the dropdown
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
