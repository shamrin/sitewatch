"""Logging setup and helpers"""


import logging
from typing import Any

from .context import pageid_var

APP_NAME = 'sitewatch'
DATE_FORMAT = "%y%m%d %H:%M:%S"
_LOGGER = logging.getLogger(APP_NAME)

# less noisy aiokafka logs
logging.getLogger('aiokafka').setLevel(logging.WARNING)


def init():
    """Initialize app logging"""

    logging.basicConfig(level=logging.INFO)

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.pageid = pageid_var.get(None)
        return record

    logging.setLogRecordFactory(record_factory)

    for handler in logging.getLogger().handlers:
        handler.setFormatter(AppLogFormatter())


class AppLogFormatter(logging.Formatter):
    def format(self, record):
        parts = ['[%(levelname)1.1s %(asctime)-15s']

        if record.name == APP_NAME:
            parts.append(f'{APP_NAME}.%(module)s:%(lineno)d]')
        else:
            parts.append('%(name)s:%(lineno)d]')

        if record.pageid is not None:
            parts.append('pageid:%(pageid)s')

        parts.append('%(message)s')

        return logging.Formatter(' '.join(parts), datefmt=DATE_FORMAT).format(record)


def info(msg: str) -> None:
    """Log info message"""
    _LOGGER.info(msg, stacklevel=2)


def warn(msg: str) -> None:
    """Log warning"""
    _LOGGER.warning(msg, stacklevel=2)


def error(msg: str, exc_info: Any = None) -> None:
    """Log error"""
    _LOGGER.error(msg, stacklevel=2, exc_info=exc_info)
