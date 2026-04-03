"""Logging configuration for EvalLedger.

Design notes
------------
* All log output is JSON (via python-json-logger) so Render's log stream and
  any downstream tool can filter and search by field.
* A ``_HealthProbeFilter`` suppresses ``request.completed`` lines for
  ``/health/live`` when ``log_health_requests=False`` (the default).
  Render polls that endpoint every ~30 s, producing ~2 880 noisy lines/day
  with no diagnostic value.
* The root log level is configurable via the ``LOG_LEVEL`` setting so it can
  be raised to ``DEBUG`` in local development without a code change.
"""

from __future__ import annotations

import logging
import logging.config
from logging import LogRecord


class _HealthProbeFilter(logging.Filter):
    """Drop ``request.completed`` log records for ``GET /health/live``.

    pythonjsonlogger attaches every ``extra=`` key as an attribute on the
    ``LogRecord``, so the middleware's ``path`` field is available here.
    """

    def filter(self, record: LogRecord) -> bool:
        return getattr(record, "path", None) != "/health/live"


def configure_logging(*, log_level: str = "INFO", log_health_requests: bool = True) -> None:
    """Initialise the root logger.

    Parameters
    ----------
    log_level:
        Python logging level name (DEBUG / INFO / WARNING / ERROR).
    log_health_requests:
        When *False*, ``/health/live`` request lines are suppressed to prevent
        Render's 30-second liveness-probe polling from flooding the log stream.
    """
    level_int: int = getattr(logging, log_level.upper(), logging.INFO)

    handler_config: dict[str, object] = {
        "class": "logging.StreamHandler",
        "formatter": "json",
        "level": level_int,
    }
    if not log_health_requests:
        handler_config["filters"] = ["no_health_probe"]

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    # List only standard fields; extra= keys are appended
                    # automatically by JsonFormatter.
                    "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "filters": {
                "no_health_probe": {
                    "()": "app.logging._HealthProbeFilter",
                }
            },
            "handlers": {"default": handler_config},
            "root": {"handlers": ["default"], "level": level_int},
        }
    )


logger = logging.getLogger("evalledger")
