import os
from typing import Optional
from dataclasses import dataclass
from datetime import timedelta, datetime
import re
import asyncio

import httpx
import asyncpg

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.helpers import create_ssl_context


@dataclass
class Page:
    id: int
    url: str
    period: timedelta
    regex: Optional[re.Pattern[str]]

@dataclass
class Report:
    page: Page
    sent: datetime
    elapsed: timedelta
    status_code: int
    found: Optional[bool] = None

async def connect_db():
    db = os.environ.get('DATABASE')
    assert db, 'DATABASE env var is missing'
    assert db.startswith('postgres://'), 'DATABASE env var is incorrect'
    return await asyncpg.connect(db)

async def fetch_urls():
    conn = await connect_db()

    await conn.execute('''
        CREATE TABLE IF NOT EXISTS page(
            pageid serial PRIMARY KEY,
            url text NOT NULL,
            period interval DEFAULT interval '5 minute',
            regex text,
            UNIQUE (url, period, regex)
        )
    ''')

    # Add page fixtures to have something interesting in the database
    await conn.executemany('''
        INSERT INTO page(url, period, regex) VALUES($1, $2, $3)
        ON CONFLICT DO NOTHING
    ''', [('https://httpbin.org/get', timedelta(minutes=5), r'Agent.*httpx'),
          ('https://google.com', timedelta(minutes=1), 'privacy'),
          ('https://google.com', timedelta(seconds=10), 'evil')])

    pages = [
        Page(row['pageid'], row['url'], row['period'], re.compile(row['regex']) if row['regex'] else None)
        for row in await conn.fetch('SELECT * FROM page')
    ]

    await conn.close()

    return pages

async def save_report(r: Report):
    conn = await connect_db()

    await conn.execute('''
        CREATE TABLE IF NOT EXISTS report(
            responseid serial PRIMARY KEY,
            pageid integer NOT NULL REFERENCES page ON DELETE CASCADE,
            elapsed interval NOT NULL,
            statuscode int NOT NULL,
            sent timestamp NOT NULL,
            found boolean
        )
    ''')

    await conn.execute('''
        INSERT INTO report(pageid, elapsed, statuscode, sent, found)
        VALUES($1, $2, $3, $4, $5)
    ''', r.page.id, r.elapsed, r.status_code, r.sent, r.found,
    )

    await conn.close()


async def check(page: Page):
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            now = datetime.now()
            r = await client.get(page.url)
            prefix = f'pageid:{page.id} url:{page.url} period:{page.period} regex:{page.regex.pattern if page.regex else None}:'
            found = None if page.regex is None else bool(page.regex.search(r.text))
            if found is not None:
                print(prefix, 'OK' if found else 'ERROR')
            report = Report(
                page = page,
                sent = now,
                elapsed = r.elapsed,
                status_code = r.status_code,
                found = found,
            )
            await save_report(report)
            print(prefix, f'waiting {sleep}s...')
            await asyncio.sleep(sleep)

KAFKA_TOPIC = 'report-topic'

def get_kafka_connection_params():
    service_uri = os.environ.get('KAFKA_SERVICE_URI')
    assert service_uri, 'KAFKA_SERVICE_URI env var is missing'
    keys_dir = os.environ.get('KAFKA_KEYS_DIR')
    assert keys_dir, 'KAFKA_KEYS_DIR env var is missing'


    ssl_files = dict(
        cafile=os.path.join(keys_dir, "ca-certificate"),
        certfile=os.path.join(keys_dir, "access-certificate"),
        keyfile=os.path.join(keys_dir, "access-key"),
    )

    print('kafka connection SSL files', ssl_files)

    params = dict(
        # See aiokafka documentation about SSL context:
        # * https://aiokafka.readthedocs.io/en/stable/#getting-started
        # * https://aiokafka.readthedocs.io/en/stable/examples/ssl_consume_produce.html
        #
        # Note: Python doesn't support loading SSL cert and key from memory.
        # As of December 2020, it's not yet implemented (8 years and counting):
        # https://bugs.python.org/issue16487, https://bugs.python.org/issue18369
        ssl_context = create_ssl_context(**ssl_files),
        bootstrap_servers = service_uri,
        security_protocol = 'SSL'
    )

    return params

async def send_one(loop):
    producer = AIOKafkaProducer(loop=loop, **get_kafka_connection_params())
    print('producer connecting to kafka cluster')
    await producer.start()
    print('producer connected')
    try:
        print('sending message')
        record = await producer.send_and_wait(KAFKA_TOPIC, b"Super message")
        print('message sent', record)
    finally:
        print('waiting for message delivery')
        await producer.stop()
        print('messages delivered (or expired)')


async def consume(loop):
    consumer = AIOKafkaConsumer(KAFKA_TOPIC, loop=loop, group_id="my-group", **get_kafka_connection_params())
    print('consumer connecting to kafka cluster')
    await consumer.start()
    print('consumer connected')
    try:
        async for msg in consumer:
            print("consumed: ", msg)
    finally:
        # Will leave consumer group; perform autocommit if enabled.
        print("stopping consumer")
        await consumer.stop()
        print("consumer stopped")


async def main():
    print('starting up')

    pages = await fetch_urls()

    for page in pages:
        asyncio.create_task(check(page))

    loop = asyncio.get_event_loop()
    asyncio.create_task(consume(loop))
    await asyncio.sleep(5)
    for _ in range(5):
        await send_one(loop)

    # TODO remove this
    await asyncio.sleep(1000)

def start():
    asyncio.run(main())
