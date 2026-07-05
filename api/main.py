"""
Continuum API gateway — thin FastAPI wrapper around the orchestrator, used
for local/demo invocation without needing a real Lambda deployment.

Versioned under /api/v1 so the wire contract can evolve without breaking
existing clients (Gradio UI, demo_run.py, chaos_demo.ps1 all target v1).
"""
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from agents.orchestrator import handle_alert
from agents.query_agent import QueryAgent
from observability.structured_logger import get_logger

log = get_logger(__name__)
app = FastAPI(
    title="Continuum",
    version="0.2.0",
    description="Agentic memory for incident response",
)

v1 = APIRouter(prefix="/api/v1")
query_agent = QueryAgent()


class Alert(BaseModel):
    correlation_id: str
    service: str
    region: str = "default"
    severity: str
    text: str


@v1.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@v1.post("/alert")
def post_alert(alert: Alert):
    result = handle_alert(alert.model_dump())
    return result


@v1.get("/incidents/open")
async def open_incidents():
    """The live query-interface beat, driven by the app itself over the
    CockroachDB Cloud Managed MCP Server (read-only) — see ADR 003."""
    try:
        result = await query_agent.list_open_incidents()
    except Exception as exc:  # MCP endpoint unreachable/misconfigured
        log.warning("mcp_query_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="MCP query interface unavailable") from exc
    return {"incidents": result.rows, "count": result.row_count}


app.include_router(v1)
