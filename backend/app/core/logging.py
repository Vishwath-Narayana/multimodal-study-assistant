import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure application-wide structured logging.

    Kept minimal for Phase 0. Later phases will extend this to emit
    structured per-request retrieval/generation traces (see docs/architecture).
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
