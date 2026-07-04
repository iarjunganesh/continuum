"""
Integration test — requires a real (or local) CockroachDB instance at
COCKROACH_DATABASE_URL. Exercises the full kill-and-recover flow end to end,
the same sequence used in the demo video.

Marked as skip by default; run explicitly against a test cluster:
    COCKROACH_DATABASE_URL=... pytest tests/integration -v -m integration
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    "COCKROACH_DATABASE_URL" not in os.environ,
    reason="requires a live CockroachDB instance — set COCKROACH_DATABASE_URL to run",
)


def test_full_recovery_cycle():
    """
    TODO (build phase):
    1. Fire an alert via handle_alert()
    2. Assert incident + step 0 are committed in CockroachDB
    3. Simulate a fresh process (no shared Python state — re-import or subprocess)
    4. Fire the same correlation_id again
    5. Assert it resumed at step 1, did not duplicate step 0
    """
    pytest.skip("Implement during build phase against a real/test CockroachDB cluster")
