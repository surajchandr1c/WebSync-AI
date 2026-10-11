import logging
import re
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter that masks tokens and credentials in logs."""

    # Patterns matching potential JWTs, Bearer headers, or secret tokens
    PATTERNS = [
        (re.compile(r"(Bearer\s+)[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*", re.IGNORECASE), r"\1[MASKED_TOKEN]"),
        (re.compile(r"(X-Worker-Auth-Token[:=]\s*)[^\s,;]+", re.IGNORECASE), r"\1[MASKED_TOKEN]"),
        (re.compile(r"(password[:=]\s*)[^\s,;]+", re.IGNORECASE), r"\1[MASKED_PASSWORD]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in self.PATTERNS:
                record.msg = pattern.sub(repl, record.msg)
        return True


def configure_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured logging for worker agent."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [worker-agent] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    logger = logging.getLogger("websync-worker")
    logger.setLevel(level)

    # Clear existing handlers to prevent duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(handler)
    logger.propagate = False

    return logger
