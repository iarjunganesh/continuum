"""
The evidence panel must render every run committed to the repo — not just the
newest one on the developer's disk.

This file exists because the Space died on startup and a green suite said
nothing was wrong. `_evidence_note` indexed `brute_warm_p50`, a field the
vector-scale rows only gained partway through the project; an older committed
run lacks it. Locally, `_newest_run` picked the newer run by mtime and the
missing field was never touched. On Hugging Face — a fresh `git clone`, where
mtimes are checkout order and mean nothing — it picked the *older* run, raised
KeyError while the Blocks were being built, and the app exited 1.

So two properties are pinned here, and both are about the gap between "works
on this machine" and "works from a clean clone":

  1. Run selection is driven by the manifest timestamp, which travels with the
     data, rather than by the filesystem, which does not survive a clone.
  2. Every committed run renders. A run predating a field is not corrupt; the
     panel must skip that figure, never crash — and never take the console's
     live panels down with it.

The UI is imported through importlib rather than `import ui.app`: it is an
app entrypoint, not a package module, and it puts the repo root on sys.path
itself when run as a script.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def app(monkeypatch_session=None):
    """Import ui/app.py once. It constructs a QueryAgent at import time, which
    only reads settings — no connection is opened until a call is made."""
    spec = importlib.util.spec_from_file_location("continuum_ui_app", REPO_ROOT / "ui" / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _committed_runs() -> list[Path]:
    runs = []
    for family in ("resilience-run", "deploy-restart-run"):
        base = REPO_ROOT / "assets" / family
        if base.exists():
            runs.extend(p.parent for p in base.glob("*/evidence") if p.is_dir())
    return sorted(runs)


def test_there_are_runs_to_check():
    """A guard on the guard: if the globbing above silently matched nothing,
    every test below would pass while checking zero runs."""
    assert _committed_runs(), "no committed evidence runs found — the tests below would be vacuous"


@pytest.mark.parametrize("run", _committed_runs(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_committed_run_renders(app, run):
    """Including runs whose schema predates fields the panel reads."""
    data = app._load_evidence(run)
    assert data, f"{run} loaded no suites"
    tiles = app._evidence_tiles(data)  # must not raise
    note = app._evidence_note(data)  # must not raise
    assert isinstance(tiles, list)
    assert isinstance(note, str)


def test_older_schema_skips_the_figure_rather_than_raising(app):
    """The exact shape that killed the Space: vector-scale without the warm
    percentiles. The note drops that clause; it does not blow up."""
    old_schema = {"vector-scale": [{"vectors": 1000, "ann_p50": 40.0, "brute_p50": 90.0}]}
    assert "C-SPANN" not in app._evidence_note(old_schema)


def test_run_selection_ignores_mtime(app, tmp_path):
    """Touching the older run must not make it "newest" — that is precisely the
    difference between this machine and a fresh clone."""
    base = tmp_path / "resilience-run"
    for name, started in (("aaaaaaaa", "2026-08-02T10:00:00+00:00"), ("bbbbbbbb", "2026-08-02T11:00:00+00:00")):
        (base / name / "evidence").mkdir(parents=True)
        (base / name / "manifest.json").write_text(json.dumps({"run_id": name, "started_utc": started}), "utf-8")

    older = base / "aaaaaaaa" / "manifest.json"
    older.touch()  # newest on disk, older by its own record
    assert app._newest_run(base).name == "bbbbbbbb"


def test_panel_failure_does_not_kill_the_app(app, monkeypatch):
    """load_evidence is evaluated while the Blocks are being built, so an
    exception here stops the process rather than blanking a section."""

    def boom():
        raise KeyError("brute_warm_p50")

    monkeypatch.setattr(app, "_render_evidence", boom)
    html = app.load_evidence()
    assert "Evidence panel unavailable" in html
    assert "KeyError" in html
