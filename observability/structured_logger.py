"""
Structured JSON logging — matches convention used in sibling repos
(argus/utils/structured_logger.py, bankers-wrapped structlog setup).
"""
import logging
import sys

import structlog

from config import settings


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str):
    configure_logging()
    return structlog.get_logger(name)
