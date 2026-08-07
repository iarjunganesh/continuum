"""Unit test for the structlog JSON setup shared by every agent."""

import json
import logging
import sys

import pytest

import observability.structured_logger as sl
from observability.structured_logger import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_logging_state():
    """Undo the module-level configure guard and the root logger between tests.

    configure_logging() is deliberately once-only at runtime, so a test that
    wants to observe configuration has to reset it or it silently measures
    whatever the previous test left behind.
    """
    saved_handlers = logging.root.handlers[:]
    saved_level = logging.root.level
    sl._CONFIGURED = False
    yield
    logging.root.handlers[:] = saved_handlers
    logging.root.setLevel(saved_level)
    sl._CONFIGURED = False


def test_get_logger_returns_a_bound_logger_usable_without_raising():
    log = get_logger("test.module")
    log.info("test_event", key="value")


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging()


def test_info_survives_a_preinstalled_root_handler(capsys):
    """The AWS Lambda case, which every other test misses.

    The Lambda Python runtime installs a root handler during init, before any
    project code imports. `logging.basicConfig()` is documented to do nothing
    when the root logger already has handlers — so without force=True the level
    is never applied, the root logger keeps its default WARNING, and because
    structlog routes through stdlib logging here, every log.info() in the
    project is discarded. The function still works and reports nothing.

    This reproduces that condition: a handler is attached first, and the test
    asserts a real JSON line still reaches stdout.
    """
    logging.root.addHandler(logging.StreamHandler(sys.stdout))
    logging.root.setLevel(logging.WARNING)

    log = get_logger("lambda.sim")
    log.info("recovered_incident_state", correlation_id="demo-incident-001")

    out = capsys.readouterr().out
    assert "recovered_incident_state" in out, "INFO was dropped — force=True lost from basicConfig"

    line = next(ln for ln in out.splitlines() if "recovered_incident_state" in ln)
    payload = json.loads(line)
    assert payload["event"] == "recovered_incident_state"
    assert payload["correlation_id"] == "demo-incident-001"
    assert payload["level"] == "info"


def test_configure_logging_sets_the_root_level_even_when_already_handled():
    logging.root.addHandler(logging.StreamHandler(sys.stdout))
    logging.root.setLevel(logging.WARNING)

    configure_logging()

    assert logging.root.level == logging.INFO
