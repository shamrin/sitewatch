"""Watch web pages and send reports to Postgres (via Kafka)"""

import sys
from datetime import datetime

import trio
import trio_asyncio
import httpx

from . import kafka
from . import db
from .model import Report, Page


def log_prefix(page: Page) -> str:
    return f'pageid:{page.id} {page.url} period:{page.period} regex:{page.regex.pattern if page.regex else None}:'


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


async def check_and_produce(producer: kafka.Producer, page: Page):
    """Periodically check page and send reports to Kafka producer, forever"""
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            report = await check_page(client, page)
            record = await producer.send_and_wait(kafka.TOPIC, report.tobytes())
            print(f'pageid:{page.id} message sent offset:{record.offset}')
            print(log_prefix(page), f'waiting {sleep}s...')
            await trio.sleep(sleep)


async def consume_and_save_reports():
    """Listen to Kafka and save reports to database"""
    async with db.connect() as conn:
        await db.init_report_table(conn)
        async with kafka.open_consumer(kafka.TOPIC) as consumer:
            print('consuming Kafka messages')
            async for msg in consumer:
                print(f'consumed: offset:{msg.offset} {msg.value}')
                report = Report.frombytes(msg.value)
                await db.save_report(conn, report)


async def watch_pages():
    """"Watch page URLs and send reports to Kafka"""
    async with db.connect() as conn, kafka.open_producer() as producer:
        print('connected to Kafka and Postgres')
        await db.init_page_table(conn)

        async with db.listen(conn, db.PAGE_CHANNEL) as notifications:
            print(f'pg: LISTEN {db.PAGE_CHANNEL}')

            # loop to allow restarting after .cancel()
            while True:
                print('fetching pages')
                pages = await db.fetch_pages(conn)
                async with trio.open_nursery() as nursery:
                    # check pages in the background
                    for page in pages:
                        nursery.start_soon(check_and_produce, producer, page)

                    # restart on `page` table changes
                    async for _ in notifications:
                        print(f'pg: received {db.PAGE_CHANNEL}, restarting')
                        nursery.cancel_scope.cancel()


async def run(mode):
    print(f'starting up {mode}')
    if mode == 'watch':
        await watch_pages()
    elif mode == 'report':
        await consume_and_save_reports()
    else:
        sys.exit(f'error: unknown mode {mode}')


def main(mode):
    trio_asyncio.run(run, mode)
