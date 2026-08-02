"""
Run-scoped evidence capture for benchmark and chaos runs.

`assets/chaos-run/README.md` already defines the convention — one folder per
run, short-id-prefixed files, numbered screenshots — but capturing it was a
manual checklist, which means evidence gets assembled after the fact from
memory. This module makes the harnesses *emit* it instead, so an artifact
cannot disagree with the run that produced it.

Every run folder carries a `manifest.json` recording provenance: the git commit
the code was at (and whether the tree was dirty), the cluster host, the
configured regions and model IDs, and the exact command line. A latency table
with no provenance is unfalsifiable; with it, a judge can tell whether the
numbers came from the code they are reading.

Layout, matching the existing convention:

    assets/<kind>-run/<short-id>/
        manifest.json
        evidence/     <short-id>_<name>.{json,md,txt}
        screenshots/  <short-id>_NN-what-it-shows.png

Secrets never enter a manifest: the database URL is reduced to host/database,
credentials stripped.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001 — provenance is best-effort, never fatal
        return ""


def _safe_dsn(dsn: str) -> str:
    """host/database only. A manifest is committed; a password must never be."""
    try:
        parts = urlsplit(dsn)
        return f"{parts.hostname}{parts.path}" if parts.hostname else "(unparseable)"
    except Exception:  # noqa: BLE001
        return "(unparseable)"


class EvidenceRun:
    """One immutable evidence folder. Create at the start of a run, write into
    it as results arrive."""

    def __init__(self, kind: str, root: Path | None = None):
        self.kind = kind
        self.short_id = uuid.uuid4().hex[:8]
        self.started = dt.datetime.now(dt.timezone.utc)
        base = root or REPO_ROOT / "assets" / f"{kind}-run"
        self.dir = base / self.short_id
        self.evidence = self.dir / "evidence"
        self.screenshots = self.dir / "screenshots"
        for d in (self.evidence, self.screenshots):
            d.mkdir(parents=True, exist_ok=True)
        self._manifest: dict = {}

    # --- writing -------------------------------------------------------
    def _path(self, name: str) -> Path:
        return self.evidence / f"{self.short_id}_{name}"

    def write_json(self, name: str, payload) -> Path:
        p = self._path(name if name.endswith(".json") else f"{name}.json")
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return p

    def write_text(self, name: str, text: str) -> Path:
        p = self._path(name)
        p.write_text(text, encoding="utf-8")
        return p

    # --- provenance ----------------------------------------------------
    def finalize(self, extra: dict | None = None) -> Path:
        """Write manifest.json. Call once, at the end, so it can record outcome
        as well as inputs."""
        from config import settings

        dirty = bool(_git("status", "--porcelain"))
        self._manifest = {
            "run_id": self.short_id,
            "kind": self.kind,
            "started_utc": self.started.isoformat(),
            "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "code": {
                "commit": _git("rev-parse", "HEAD"),
                "commit_short": _git("rev-parse", "--short", "HEAD"),
                "describe": _git("describe", "--tags", "--always"),
                # A dirty tree means the evidence does NOT correspond to any
                # commit anyone else can check out. Recorded, not hidden.
                "working_tree_dirty": dirty,
            },
            "environment": {
                "python": sys.version.split()[0],
                "platform": sys.platform,
                "cluster": _safe_dsn(settings.cockroach_database_url),
                "aws_region": settings.aws_region,
                "bedrock_region": settings.bedrock_region,
                "embedding_model": settings.bedrock_embedding_model_id,
                "reasoning_model": settings.bedrock_reasoning_model_id,
                "lambda_function": settings.lambda_function_name,
                "step_execution_seconds": settings.step_execution_seconds,
                "max_remediation_steps": settings.max_remediation_steps,
            },
            "command": " ".join([Path(sys.argv[0]).name, *sys.argv[1:]]),
            "files": sorted(p.name for p in self.evidence.iterdir() if p.is_file()),
            "screenshots": sorted(p.name for p in self.screenshots.iterdir() if p.is_file()),
        }
        if extra:
            self._manifest["results"] = extra

        path = self.dir / "manifest.json"
        path.write_text(json.dumps(self._manifest, indent=2, default=str), encoding="utf-8")

        # A .gitkeep keeps the screenshots folder in git while it's still empty,
        # so the run folder is complete even before any are captured.
        keep = self.screenshots / ".gitkeep"
        if not any(self.screenshots.iterdir()):
            keep.touch()
        return path

    def __repr__(self) -> str:
        return f"<EvidenceRun {self.kind}/{self.short_id} at {self.dir.relative_to(REPO_ROOT)}>"


def new_run(kind: str) -> EvidenceRun:
    if not os.getenv("CONTINUUM_EVIDENCE", "1") == "1":
        raise RuntimeError("evidence capture disabled via CONTINUUM_EVIDENCE=0")
    return EvidenceRun(kind)
