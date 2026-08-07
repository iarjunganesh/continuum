"""
The KPI tiles must count the table, not the page.

This file exists because they didn't, for a month, and nothing caught it.

`load_dashboard` fetches the card feed with a `LIMIT` — a pagination cap chosen
for the 3-up grid (8 rows × 3). The tiles were then summed from that same
already-truncated result set, because it was the list already in scope. So
"Steps committed · durable in CockroachDB" was really "steps belonging to the 24
most recently updated incidents", i.e. a headline claim about durability whose
value was set by the CSS grid width.

Two ways that goes wrong, and the second is the bad one:

  1. It understates. A cluster holding 44 incidents and 128 executed steps
     rendered 22 and 68 — a project whose entire thesis is durable memory,
     halving its own numbers on the page judges open first.

  2. It *decreases when rows are written*. A benchmark run wrote 18 incidents to
     the demo cluster; they flooded the newest-24 window and evicted real
     resolved incidents, so the tile labelled "closed by the agent" fell from 21
     to 6 while the true resolved count had only gone up. A metric that moves
     backwards when unrelated work happens is worse than a missing metric.

So the property pinned here is that the tiles come from an aggregate over the
whole table and are *not* derivable from the feed rows. The fixtures below make
those two answers deliberately different — every tile value is unreachable by
summing the feed — so a regression to the old code fails loudly rather than
looking plausible.

The UI is imported through importlib rather than `import ui.app`: it is an app
entrypoint, not a package module, and it puts the repo root on sys.path itself
when run as a script (same reasoning as test_ui_evidence.py).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Cluster truth the fake connection reports. Chosen so that no tile value can be
# reconstructed from the feed: the feed carries FEED_LIMIT incidents of 1 step
# each, so a feed-derived "steps committed" is FEED_LIMIT, never 128.
TRUTH = {
    "open_n": 2,
    "resolved_n": 42,
    "total_n": 44,
    "executing_n": 1,
    "executed_n": 128,
}


_DEFAULT = object()  # "use TRUTH", as distinct from "the aggregate returned no row"


@pytest.fixture(scope="module")
def app():
    spec = importlib.util.spec_from_file_location("continuum_ui_kpis_app", REPO_ROOT / "ui" / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _feed_rows(n: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "incident_id": f"0000000{i:04d}-0000-0000-0000-000000000000",
            "service": "checkout-api",
            "region": "eu-central-1",
            "severity": "high",
            "state": "resolved",
            "summary": "Elevated p99 latency on checkout-api",
            "opened_at": now - timedelta(days=i + 1),
            "updated_at": now - timedelta(days=i),
            "steps_executed": 1,
            "steps_executing": 0,
        }
        for i in range(n)
    ]


class _FakeCursor:
    """Dispatches on SQL text so the three statements can return different
    shapes, and records what was asked."""

    def __init__(self, feed: list[dict], totals: dict | None):
        self.feed = feed
        self.totals = totals
        self.statements: list[str] = []
        self._result: list[dict] = []

    def execute(self, sql, params=None):
        self.statements.append(" ".join(sql.split()))
        if "FROM incidents i" in sql:
            self._result = self.feed
        elif "step_index" in sql:
            self._result = [
                {
                    "incident_id": r["incident_id"],
                    "step_index": 0,
                    "action": "restart_pods",
                    "status": "executed",
                    "created_at": r["updated_at"],
                }
                for r in self.feed
            ]
        else:  # the aggregate
            self._result = [self.totals] if self.totals is not None else []

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_conn(cursor):
    conn = MagicMock()
    conn.__enter__ = lambda self: self
    conn.__exit__ = lambda self, *exc: False
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def dashboard(app):
    """Renders load_dashboard against a fake cluster; yields (cursor, outputs)."""

    def _run(feed_n: int | None = None, totals: dict | None = _DEFAULT):
        # `totals=None` means the aggregate returns no row at all — distinct from
        # "use the default", which is what _DEFAULT is for.
        feed = _feed_rows(app.FEED_LIMIT if feed_n is None else feed_n)
        cursor = _FakeCursor(feed, TRUTH if totals is _DEFAULT else totals)
        with patch.object(app, "_connect", return_value=_fake_conn(cursor)):
            return cursor, app.load_dashboard()

    return _run


def _tile_numbers(kpis_html: str) -> list[int]:
    return [int(n) for n in re.findall(r">\s*(\d+)\s*<", kpis_html)]


def test_tiles_report_the_table_not_the_page(dashboard):
    """Open, in-flight, resolved, steps committed — in render order."""
    _, (_banner, kpis, _cards, _dd) = dashboard()
    assert _tile_numbers(kpis)[:4] == [
        TRUTH["open_n"],
        TRUTH["executing_n"],
        TRUTH["resolved_n"],
        TRUTH["executed_n"],
    ]


def test_tiles_are_not_reachable_by_summing_the_feed(app, dashboard):
    """The regression shape. Under the old code every one of these tiles was a
    sum over the truncated feed, so pinning that they differ from it is what
    actually fails if someone reverts."""
    _, (_banner, kpis, _cards, _dd) = dashboard()
    rendered = _tile_numbers(kpis)[:4]

    # What the old, feed-derived implementation would have produced: the feed is
    # FEED_LIMIT resolved incidents of one executed step each.
    feed_derived = [0, 0, app.FEED_LIMIT, app.FEED_LIMIT]
    assert rendered != feed_derived
    assert rendered[3] > app.FEED_LIMIT, "steps committed must be able to exceed the page size"


def test_the_aggregate_is_actually_queried(dashboard):
    """Guards the guard: if the totals statement stopped being issued, the tiles
    would fall back to zeros and several assertions above could still pass on a
    cluster that happens to be empty."""
    cursor, _ = dashboard()
    aggregates = [s for s in cursor.statements if "count(*) FROM incidents)" in s]
    assert aggregates, f"no table-wide aggregate was issued; statements: {cursor.statements}"


def test_feed_caption_declares_the_window(app, dashboard):
    """Showing 24 of 44 silently is what let the two numbers disagree unnoticed."""
    _, (_banner, _kpis, cards, _dd) = dashboard()
    caption = re.search(r'<div class="cx-feedcap">(.*?)</div>', cards, re.S)
    assert caption, "paginated feed rendered no caption"
    text = caption.group(1)
    assert str(app.FEED_LIMIT) in text and str(TRUTH["total_n"]) in text


def test_no_caption_when_the_feed_is_the_whole_table(dashboard):
    """Don't tell the viewer they're seeing a subset when they aren't."""
    totals = {**TRUTH, "total_n": 3}
    _, (_banner, _kpis, cards, _dd) = dashboard(feed_n=3, totals=totals)
    assert "cx-feedcap" not in cards


def test_banner_counts_in_flight_steps_from_the_table(dashboard):
    """The banner asserts 'N remediation step(s) in-flight' as a fact about
    CockroachDB. A step executing on an incident outside the newest page is
    still in-flight, and is exactly the one a kill would land on."""
    totals = {**TRUTH, "executing_n": 3}
    _, (banner, _kpis, _cards, _dd) = dashboard(totals=totals)
    assert "3 remediation steps in-flight" in banner


def test_empty_cluster_renders_zeros_not_a_crash(dashboard):
    """`fetchone()` returning None must degrade to zeros — the Space stays up."""
    _, (banner, kpis, cards, _dd) = dashboard(feed_n=0, totals=None)
    assert _tile_numbers(kpis)[:4] == [0, 0, 0, 0]
    assert "No incidents yet" in cards
    assert "No steps in-flight" in banner


# ── Provenance badges ────────────────────────────────────────────────────────
# Same rule as the tiles: a badge states something about the durable row, so it
# reads a column or it does not render. The failure this guards against is not
# a crash — it is a badge that looks authoritative and asserts something the
# database never said.


def _step(**over):
    base = {
        "incident_id": "0000000000-0000-0000-0000-000000000000",
        "step_index": 0,
        "action": "restart_pods",
        "status": "executed",
        "created_at": None,
        "reasoning_source": None,
        "correlation_source": None,
        "precedent_id": None,
        "precedent_distance": None,
        "precedent_rank": None,
        "precedents_considered": None,
        "resumed": None,
        "reasoning_model_id": None,
        "embedding_model_id": None,
        "runtime": None,
    }
    return {**base, **over}


def test_resumed_badge_renders_only_from_the_durable_flag(app):
    """The differentiator. It is a boolean in `detail`, and it was invisible on
    the page for the entire project."""
    row = {"embedding_model": None}
    assert "resumed after kill" not in app._provenance(row, [_step()])
    assert "resumed after kill" in app._provenance(row, [_step(resumed="true")])


def test_distance_is_suppressed_without_an_attestable_vector_space(app):
    """A distance means nothing outside the embedding model that produced it,
    and this corpus has been re-embedded once — every distance moved from ~1.40
    to ~0.64. Rank still renders: 'closest of 5' is true in any space."""
    prec = _step(
        reasoning_source="bedrock",
        precedent_id="abc12345",
        precedent_distance="1.4034",
        precedent_rank="0",
        precedents_considered="5",
    )
    legacy = app._provenance({"embedding_model": None}, [prec])
    assert "#1 of 5" in legacy
    assert "1.4034" not in legacy, "an uninterpretable distance was rendered as a similarity"

    attested = app._provenance(
        {"embedding_model": None}, [_step(**{**prec, "embedding_model_id": "amazon.titan-embed-text-v2:0"})]
    )
    assert "d=1.4034" in attested


def test_embedding_model_is_printed_verbatim_not_prettified(app):
    """It read `synthetic-deterministic` for a month while the docs said Titan.
    A badge that cannot say the unflattering thing is decoration."""
    assert "synthetic-deterministic" in app._provenance({"embedding_model": "synthetic-deterministic"}, [])
    assert "titan-embed-text-v2" in app._provenance({"embedding_model": "amazon.titan-embed-text-v2:0"}, [])


def test_runtime_badge_is_not_invented(app):
    """`runtime` comes from the orchestrator reading Lambda's own env var. No
    field, no badge — the UI must never guess where a step executed."""
    assert "lambda" not in app._provenance({"embedding_model": None}, [_step(reasoning_source="bedrock")])
    assert "lambda" in app._provenance({"embedding_model": None}, [_step(reasoning_source="bedrock", runtime="lambda")])


def test_no_provenance_row_when_nothing_is_known(app):
    """An empty bordered strip under every card is worse than no strip."""
    assert app._provenance({"embedding_model": None}, [_step()]) == ""


def test_malformed_numerics_do_not_take_the_card_down(app):
    """JSONB read back as text. One bad value must cost one badge, not the feed."""
    out = app._provenance(
        {"embedding_model": None},
        [
            _step(
                precedent_id="abc",
                precedent_rank="not-a-number",
                precedents_considered="five",
                precedent_distance="NaN-ish",
            )
        ],
    )
    assert isinstance(out, str)
