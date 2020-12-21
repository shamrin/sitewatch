import os
import sys
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import timedelta, datetime
import re
import asyncio
import json

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
    pageid: int
    sent: datetime
    elapsed: timedelta
    status_code: int
    found: Optional[bool] = None

    def tobytes(self) -> bytes:
        d = asdict(self)
        d['elapsed'] = d['elapsed'].total_seconds()
        d['sent'] = d['sent'].isoformat()
        return json.dumps(d).encode('utf8')

    @classmethod
    def frombytes(cls, raw: bytes) -> 'Report':
        d = json.loads(str(raw, 'utf8'))
        return Report(
            pageid=d['pageid'],
            sent=datetime.fromisoformat(d['sent']),
            elapsed=timedelta(seconds=d['elapsed']),
            status_code=d['status_code'],
            found=d['found'],
        )

async def connect_db():
    db = os.environ.get('PG_SERVICE_URI')
    assert db, 'PG_SERVICE_URI env var is missing'
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
          ('https://google.com', timedelta(minutes=10), 'evil')])

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
    ''', r.pageid, r.elapsed, r.status_code, r.sent, r.found,
    )

    await conn.close()


async def check(page: Page):
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            now = datetime.utcnow()
            r = await client.get(page.url)
            prefix = f'pageid:{page.id} url:{page.url} period:{page.period} regex:{page.regex.pattern if page.regex else None}:'
            found = None if page.regex is None else bool(page.regex.search(r.text))
            if found is not None:
                print(prefix, 'OK' if found else 'ERROR')
            report = Report(
                pageid = page.id,
                sent = now,
                elapsed = r.elapsed,
                status_code = r.status_code,
                found = found,
            )
            await send_one(report.tobytes())
            await save_report(report)
            print(prefix, f'waiting {sleep}s...')
            await asyncio.sleep(sleep)

KAFKA_TOPIC = 'report-topic'

def get_kafka_connection_params():
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
        ssl_context = create_ssl_context(
            cafile=os.path.join(keys_dir, "ca.pem"),
            certfile=os.path.join(keys_dir, "service.cert"),
            keyfile=os.path.join(keys_dir, "service.key"),
        ),
        bootstrap_servers = service_uri,
        security_protocol = 'SSL',
    )

    return params

async def send_one(message: bytes):
    loop = asyncio.get_event_loop()
    producer = AIOKafkaProducer(loop=loop, **get_kafka_connection_params())
    # print('producer connecting to kafka cluster')
    await producer.start()
    # print('producer connected')
    try:
        # print('sending message')
        record = await producer.send_and_wait(KAFKA_TOPIC, message)
        print('message sent', record)
    finally:
        print('waiting for message delivery')
        await producer.stop()
        print('messages delivered (or expired)')

async def consume():
    loop = asyncio.get_event_loop()
    consumer = AIOKafkaConsumer(KAFKA_TOPIC, loop=loop, group_id="my-group", **get_kafka_connection_params())
    print('consumer connecting to kafka cluster')
    await consumer.start()
    print('consumer connected')
    try:
        async for msg in consumer:
            print("consumed: ", msg)
            report = Report.frombytes(msg.value)
            await save_report(report)
    finally:
        # Will leave consumer group; perform autocommit if enabled.
        print("stopping consumer")
        await consumer.stop()
        print("consumer stopped")


async def main(mode):
    print(f'starting up {mode}')

    if mode == 'watch':
        pages = await fetch_urls()
        for page in pages:
            asyncio.create_task(check(page))
    elif mode == 'report':
        asyncio.create_task(consume())
    else:
        sys.exit(f'unknown mode {mode}')

    # TODO remove this
    await asyncio.sleep(1000)

def start(mode):
    asyncio.run(main(mode))
