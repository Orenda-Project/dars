"""
Structured logging configuration for the Chapter Planning Engine (CPE).

Usage in any module:
    from logging_config import get_logger
    logger = get_logger(__name__)

Log levels used:
    logger.debug(...)   — verbose detail (prompts, parsed JSON, timings)
    logger.info(...)    — normal flow milestones (request accepted, plan returned)
    logger.warning(...) — degraded but recoverable
    logger.error(...)   — failures (exception caught) — always with exc_info=True
"""
import logging
import sys
import os


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger wired to the shared handler."""
    return logging.getLogger(name)


def _configure():
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. uvicorn reloaded the module)
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # stdout handler — captured by the platform (Railway / journald)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_configure()
