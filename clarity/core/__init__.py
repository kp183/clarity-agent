"""Structured logging configuration for Clarity."""

import structlog
import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging for the entire application."""
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Auto-configure on import
configure_logging()
logger = structlog.get_logger()
