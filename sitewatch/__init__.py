"""Watch web pages and send reports to Postgres (via Kafka)"""

import sys
from datetime import datetime
import logging

import trio
import trio_asyncio
import httpx

from . import kafka
from . import db
from .model import Report, Page, ValidationError, ParseError
from .context import pageid_var
from .log import init_logging

log = logging.getLogger(__name__)


async def check_page(client: httpx.AsyncClient, page: Page) -> Report:
    """Check page once"""
    now = datetime.utcnow()
    response = await client.get(page.url)
    found = None
    if page.regex is not None:
        found = bool(page.regex.search(response.text))
        log.info(f'/{page.regex.pattern}/ {"OK" if found else "ERROR"}')

    return Report(
        pageid=page.id,
        sent=now,
        elapsed=response.elapsed.total_seconds(),
        status_code=response.status_code,
        found=found,
    )


async def watch_page(producer: kafka.Producer, page: Page):
    """Continuously check page and send reports to Kafka"""
    pageid_var.set(page.id)
    log.info(f'start watching page {page.url}')
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            log.info('checking page')
            report = await check_page(client, page)
            record = await producer.send_and_wait(kafka.TOPIC, report.tobytes())
            log.info(f'page report sent offset:{record.offset}')
            log.info(f'waiting {sleep}s...')
            await trio.sleep(sleep)


async def watch_pages():
    """"Watch page URLs and send reports to Kafka"""
    async with db.connect() as conn, kafka.open_producer() as producer:
        log.info('connected to Kafka and Postgres')
        await db.init_page_table(conn)

        async with db.listen(conn, db.PAGE_CHANNEL) as notifications:
            log.info(f'pg: LISTEN {db.PAGE_CHANNEL}')

            # loop to allow restarting after .cancel()
            while True:
                log.info('fetching pages')
                pages = await db.fetch_pages(conn)
                async with trio.open_nursery() as nursery:
                    # check pages in the background
                    for page in pages:
                        nursery.start_soon(watch_page, producer, page)

                    # restart on `page` table changes
                    async for _ in notifications:
                        log.info(f'pg: received {db.PAGE_CHANNEL}, restarting')
                        nursery.cancel_scope.cancel()


async def watch_reports():
    """Listen to Kafka and save reports to database"""
    async with db.connect() as conn:
        await db.init_report_table(conn)
        async with kafka.open_consumer(kafka.TOPIC) as consumer:
            log.info('consuming Kafka messages')
            async for msg in consumer:
                log.info(f'consumed message with offset {msg.offset}: {msg.value}')
                try:
                    report = Report.frombytes(msg.value)
                except ValidationError as e:
                    log.warn(f'validation error {dict(e)}: {msg.value}')
                except ParseError as e:
                    index = e.messages()[0].start_position.char_index
                    log.warn(f'parse error "{e}" at char {index}: {msg.value}')
                else:
                    await db.save_report(conn, report)
                    log.info(f'saved to db: {report}')


async def run(mode):
    init_logging()
    log.info(f'starting up {mode}')
    if mode == 'watch':
        await watch_pages()
    elif mode == 'report':
        await watch_reports()
    else:
        sys.exit(f'error: unknown mode {mode}')


def main(mode):
    trio_asyncio.run(run, mode)
