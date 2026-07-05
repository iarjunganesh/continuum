"""Unit test for the structlog JSON setup shared by every agent."""
from observability.structured_logger import configure_logging, get_logger


def test_get_logger_returns_a_bound_logger_usable_without_raising():
    log = get_logger("test.module")
    log.info("test_event", key="value")


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging()
