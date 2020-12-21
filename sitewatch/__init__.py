import sys
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import timedelta, datetime
import re
import asyncio
import json

import httpx
import asyncpg

from .kafka import KafkaProducer, KafkaConsumer, kafka_params
from .db import init_page_table, init_report_table, postgres_service

@dataclass
class Page:
    id: int
    url: str
    period: timedelta
    regex: Optional[re.Pattern[str]]

class ValidationError(Exception):
    pass

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
        try:
            d = json.loads(str(raw, 'utf8'))
        except json.JSONDecodeError:
            raise ValidationError('invalid json')
        try:
            elapsed = timedelta(seconds=d['elapsed'])
        except TypeError:
            raise ValidationError('invalid duration')
        try:
            sent = datetime.fromisoformat(d['sent'])
        except ValueError:
            raise ValidationError('invalid datetime')

        return cls(
            pageid=d['pageid'],
            sent=sent,
            elapsed=elapsed,
            status_code=d['status_code'],
            found=d['found'],
        )

async def fetch_pages():
    async with asyncpg.create_pool(postgres_service()) as pool:
        await init_page_table(pool)
        pages = [
            Page(row['pageid'], row['url'], row['period'], re.compile(row['regex']) if row['regex'] else None)
            for row in await pool.fetch('SELECT * FROM page')
        ]

        return pages

async def save_report(conn, r: Report):
    await conn.execute('''
        INSERT INTO report(pageid, elapsed, statuscode, sent, found)
        VALUES($1, $2, $3, $4, $5)
    ''', r.pageid, r.elapsed, r.status_code, r.sent, r.found,
    )
    print(f'saved to db: {r}')

def log_prefix(page: Page) -> str:
    return f'pageid:{page.id} url:{page.url} period:{page.period} regex:{page.regex.pattern if page.regex else None}:'

async def check_page(client: httpx.AsyncClient, page: Page) -> Report:
    now = datetime.utcnow()
    r = await client.get(page.url)
    found = None if page.regex is None else bool(page.regex.search(r.text))
    if found is not None:
        print(log_prefix(page), 'OK' if found else 'ERROR')
    return Report(
        pageid = page.id,
        sent = now,
        elapsed = r.elapsed,
        status_code = r.status_code,
        found = found,
    )

async def check_and_produce(producer: KafkaProducer, page: Page):
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            report = await check_page(client, page)
            record = await producer.send_and_wait(KAFKA_TOPIC, report.tobytes())
            print('message sent', record)
            print(log_prefix(page), f'waiting {sleep}s...')
            await asyncio.sleep(sleep)

KAFKA_TOPIC = 'report-topic'

async def consume_and_save_reports():
    loop = asyncio.get_event_loop()

    async with asyncpg.create_pool(postgres_service()) as pool:
        await init_report_table(pool)
        async with KafkaConsumer(KAFKA_TOPIC, loop=loop, group_id="my-group", **kafka_params()) as consumer:
            print('consuming Kafka messages')
            async for msg in consumer:
                print("consumed: ", msg)
                report = Report.frombytes(msg.value)
                await save_report(pool, report)


async def main(mode):
    print(f'starting up {mode}')
    loop = asyncio.get_event_loop()

    if mode == 'watch':
        pages = await fetch_pages()
        async with KafkaProducer(loop=loop, **kafka_params()) as producer:
            print('connected to Kafka')
            await asyncio.gather(*[
                check_and_produce(producer, page) for page in pages
            ])
    elif mode == 'report':
        await consume_and_save_reports()
    else:
        sys.exit(f'error: unknown mode {mode}')

def start(mode):
    asyncio.run(main(mode))
