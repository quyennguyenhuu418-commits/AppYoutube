"""
Centralized logging setup. Call `configure_logging()` once at app startup.

Format: `YYYY-MM-DD HH:MM:SS LEVEL [logger] message`. We deliberately keep
this minimal so a non-coder can grep logs without learning a logging DSL.
"""
from __future__ import annotations

import logging
import sys

from app.core.config import settings


_CONFIGURED = False


def configure_logging() -> None:
    """Idempotently configure root logging.

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy libraries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper; also ensures logging is configured."""
    configure_logging()
    return logging.getLogger(name)
