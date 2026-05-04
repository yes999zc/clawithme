"""Structured logging with structlog + trace_id propagation."""

import uuid

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with trace context propagation.

    Each request gets a trace_id. Bind it with:
        logger = logger.bind(trace_id=str(uuid.uuid4()))
    All subsequent calls from that logger carry the trace_id.
    """
    import logging
    logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(**ctx) -> structlog.BoundLogger:
    """Get a logger with optional initial context."""
    logger = structlog.get_logger()
    if ctx:
        logger = logger.bind(**ctx)
    return logger


def new_trace_id() -> str:
    """Generate a new trace_id for a request pipeline."""
    return str(uuid.uuid4())
