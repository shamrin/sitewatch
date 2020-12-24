"""Kafka producer and consumer, with service-specific settings and trio compat"""

import os
import asyncio

from trio_asyncio import aio_as_trio
import aiokafka
from aiokafka.helpers import create_ssl_context

KAFKA_TOPIC = 'report-topic'


def open_producer():
    return KafkaProducer(loop=asyncio.get_event_loop(), **kafka_params())


def open_consumer(topic):
    return KafkaConsumer(
        topic, group_id='my-group', loop=asyncio.get_event_loop(), **kafka_params()
    )


class KafkaProducer(aiokafka.AIOKafkaProducer):
    """Same as aiokafka class, but trio-compatible"""

    # Also provides a work-around until this fix is merged:
    # https://github.com/aio-libs/aiokafka/pull/701

    @aio_as_trio
    async def __aenter__(self):
        await self.start()
        return self

    @aio_as_trio
    async def __aexit__(self):
        await self.stop()

    @aio_as_trio
    async def send_and_wait(self, *arg, **kw):
        return await super().send_and_wait(*arg, **kw)


class KafkaConsumer(aiokafka.AIOKafkaConsumer):
    """Same as aiokafka class, but trio-compatible"""

    @aio_as_trio
    async def __aenter__(self):
        await self.start()
        return aio_as_trio(self)

    @aio_as_trio
    async def __aexit__(self):
        await self.stop()


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
