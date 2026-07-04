"""
Continuum API gateway — thin FastAPI wrapper around the orchestrator, used
for local/demo invocation without needing a real Lambda deployment.

Versioned under /api/v1 so the wire contract can evolve without breaking
existing clients (Gradio UI, demo_run.py, chaos_demo.ps1 all target v1).
"""
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from agents.orchestrator import handle_alert
from observability.structured_logger import get_logger

log = get_logger(__name__)
app = FastAPI(
    title="Continuum",
    version="0.2.0",
    description="Agentic memory for incident response",
)

v1 = APIRouter(prefix="/api/v1")


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


app.include_router(v1)
