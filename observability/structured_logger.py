"""
Structured JSON logging for Continuum — structlog configured for JSON
output so every agent/API log line is machine-parseable.
"""

import logging
import sys

import structlog

from config import settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    # force=True is load-bearing on AWS Lambda and a no-op everywhere else.
    #
    # basicConfig() does nothing when the root logger already has a handler,
    # and the Lambda Python runtime installs one during init — before any of
    # our code imports. So on Lambda the level was never applied, the root
    # logger kept its default WARNING, and because structlog routes through
    # stdlib logging here, every log.info() in the project was discarded.
    # The function worked correctly and reported nothing: CloudWatch held only
    # Lambda's own START/END/REPORT lines, so `recovered_incident_state` — the
    # log line that evidences the recovery contract on the real runtime — could
    # never appear. Locally there is no pre-installed handler, so tests and
    # every local run looked fine, which is exactly why this survived.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level, force=True)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    _CONFIGURED = True


def get_logger(name: str):
    configure_logging()
    return structlog.get_logger(name)
