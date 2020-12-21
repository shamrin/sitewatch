"""Watch web pages and send reports to Postgres (via Kafka)"""

import sys
from datetime import datetime
import asyncio

import trio
import trio_asyncio
import httpx

from .kafka import KafkaProducer, KafkaConsumer, kafka_params, KAFKA_TOPIC
from .db import (
    create_pool,
    init_report_table,
    postgres_service,
    fetch_pages,
    save_report,
)
from .model import Report, Page


def log_prefix(page: Page) -> str:
    return f'pageid:{page.id} url:{page.url} period:{page.period} regex:{page.regex.pattern if page.regex else None}:'


async def check_page(client: httpx.AsyncClient, page: Page) -> Report:
    """Check page once"""
    now = datetime.utcnow()
    r = await client.get(page.url)
    found = None if page.regex is None else bool(page.regex.search(r.text))
    if found is not None:
        print(log_prefix(page), 'OK' if found else 'ERROR')
    return Report(
        pageid=page.id,
        sent=now,
        elapsed=r.elapsed,
        status_code=r.status_code,
        found=found,
    )


async def check_and_produce(producer: KafkaProducer, page: Page):
    """Periodically check page and send reports to Kafka producer, forever"""
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            report = await check_page(client, page)
            record = await producer.send_and_wait(KAFKA_TOPIC, report.tobytes())
            print('message sent', record)
            print(log_prefix(page), f'waiting {sleep}s...')
            await trio.sleep(sleep)


async def consume_and_save_reports():
    """Listen to Kafka and save reports to database"""
    loop = asyncio.get_event_loop()

    async with create_pool(postgres_service()) as pool:
        await init_report_table(pool)
        async with KafkaConsumer(
            KAFKA_TOPIC, loop=loop, group_id="my-group", **kafka_params()
        ) as consumer:
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
            async with trio.open_nursery() as nursery:
                for page in pages:
                    nursery.start_soon(check_and_produce, producer, page)
    elif mode == 'report':
        await consume_and_save_reports()
    else:
        sys.exit(f'error: unknown mode {mode}')


def start(mode):
    trio_asyncio.run(main, mode)
