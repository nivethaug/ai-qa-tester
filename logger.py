"""
AI QA Tester - Structured Logger
Uses asyncio-safe logging with color tags.
"""

import logging
import sys

from config import LOG_LEVEL

LOG_FORMAT = "%(asctime)s [%(tag)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class TagFilter(logging.Filter):
    """Inject 'tag' from extra into log record."""

    def filter(self, record):
        record.tag = getattr(record, "tag", "APP")
        return True


def setup_logger(name: str = "ai_qa_tester") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.addFilter(TagFilter())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)

    return logger


log = setup_logger()


def log_event(tag: str, msg: str):
    log.info(msg, extra={"tag": tag})


def log_error(tag: str, msg: str):
    log.error(msg, extra={"tag": tag})
