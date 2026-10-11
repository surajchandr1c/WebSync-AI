"""Security-hardened logging configuration with automated credential and token redaction."""

import logging
import re
from coordinator.config import settings


class SensitiveDataFilter(logging.Filter):
    """Filter that masks tokens, passwords, and sensitive connection strings in log output."""

    PATTERNS = [
        # Bearer tokens / JWTs
        (re.compile(r"(Bearer\s+)[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*", re.IGNORECASE), r"\1[REDACTED_JWT]"),
        # X-Worker-Auth-Token headers / params
        (re.compile(r"(X-Worker-Auth-Token[:=]\s*)[^\s,;]+", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
        # Passwords in query params, json, or logs (password=xxx, password: xxx, password 'xxx')
        (re.compile(r"(password[\"']?\s*[:=\s]\s*[\"']?)[^\"'\s,;]+([\"']?)", re.IGNORECASE), r"\1[REDACTED_PASSWORD]\2"),
        # Database connection strings with passwords (postgres://user:pass@host)
        (re.compile(r"(://[^:]+:)[^@]+(@)", re.IGNORECASE), r"\1[REDACTED_SECRET]\2"),
        # Coordinator secret key / dev token
        (re.compile(r"(COORDINATOR_SECRET_KEY[:=]\s*)[^\s,;]+", re.IGNORECASE), r"\1[REDACTED_SECRET]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in self.PATTERNS:
                record.msg = pattern.sub(repl, record.msg)
        return True


def setup_coordinator_logging(log_level: str = None) -> None:
    """Initialize structured logging with security redaction filter."""
    lvl_str = log_level or settings.LOG_LEVEL
    level = getattr(logging, lvl_str.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Attach filter to all existing handlers or create standard stream handler
    redaction_filter = SensitiveDataFilter()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(redaction_filter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.addFilter(redaction_filter)
