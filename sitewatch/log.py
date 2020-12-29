"""Logging setup and helpers"""


import logging

from .context import pageid_var


def init_logging():
    """Initialize app logging"""

    # configure Tornado-style format
    logging.basicConfig(
        level=logging.INFO,
        datefmt="%y%m%d %H:%M:%S",
        format='[%(levelname)1.1s %(asctime)-15s %(name)s:%(lineno)d] %(message)s',
    )

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        pageid = pageid_var.get(None)
        if pageid is not None:
            record.msg += f' pageid:{pageid}'
        return record

    # append pageid to each message
    logging.setLogRecordFactory(record_factory)

    # less noisy aiokafka logs
    logging.getLogger('aiokafka').setLevel(logging.WARNING)
