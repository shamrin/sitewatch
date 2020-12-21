"""Kafka producer and consumer, with service-specific settings"""

import os

import aiokafka
from aiokafka import AIOKafkaConsumer as KafkaConsumer
from aiokafka.helpers import create_ssl_context

KAFKA_TOPIC = 'report-topic'


# Work-around until fix is merged: https://github.com/aio-libs/aiokafka/pull/701
class KafkaProducer(aiokafka.AIOKafkaProducer):
    """Same as aiokafka class, but works as a context manager"""

    async def __aenter__(self):
        await self.start()
        return self


def kafka_params():
    """Return Kafka connection params"""

    service_uri = os.environ.get('KAFKA_SERVICE_URI')
    assert service_uri, 'KAFKA_SERVICE_URI env var is missing'
    keys_dir = os.environ.get('KAFKA_CERT_DIR')
    assert keys_dir, 'KAFKA_CERT_DIR env var is missing'

    params = dict(
        # See aiokafka documentation about SSL context:
        # * https://aiokafka.readthedocs.io/en/stable/#getting-started
        # * https://aiokafka.readthedocs.io/en/stable/examples/ssl_consume_produce.html
        #
        # Note: Python doesn't support loading SSL cert and key from memory.
        # As of December 2020, it's not yet implemented (8 years and counting):
        # https://bugs.python.org/issue16487, https://bugs.python.org/issue18369
        ssl_context=create_ssl_context(
            cafile=os.path.join(keys_dir, "ca.pem"),
            certfile=os.path.join(keys_dir, "service.cert"),
            keyfile=os.path.join(keys_dir, "service.key"),
        ),
        bootstrap_servers=service_uri,
        security_protocol='SSL',
    )

    return params


__all__ = ['KafkaConsumer', 'KafkaProducer']
