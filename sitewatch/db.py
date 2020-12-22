"""Datatabase connection, tables init and main operations"""

import os
from datetime import timedelta
import re
from typing import List
from contextlib import asynccontextmanager

import trio
import triopg

from .model import Report, Page

PAGE_CHANNEL = 'page.change'


def pg_service() -> str:
    db = os.environ.get('PG_SERVICE_URI')
    assert db, 'PG_SERVICE_URI env var is missing'
    return db


def connect():
    return triopg.connect(pg_service())


@asynccontextmanager
async def listen(conn, channel):
    """LISTEN on `channel` notifications and return memory channel to iterate over

    For example:

    async with listen(conn, 'some.changes') as changes:
        async for change in changes:
            print('Postgres notification received:', change)
    """

    # based on https://gitter.im/python-trio/general?at=5fe10d762084ee4b78650fc8

    send_channel, receive_channel = trio.open_memory_channel(1)

    def _listen_callback(c, pid, chan, payload):
        send_channel.send_nowait(payload)

    await conn.add_listener(channel, _listen_callback)
    async with send_channel:
        yield receive_channel
    await conn.remove_listener(channel, _listen_callback)


async def init_page_table(conn):
    """Initialize `page` table and add fixtures (idempotent)"""

    await conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS page(
            pageid serial PRIMARY KEY,
            url text NOT NULL,
            period interval DEFAULT interval '5 minute',
            regex text,
            UNIQUE (url, period, regex)
        )
    '''
    )

    # send NOTIFY on page table modifications
    # based on https://tapoueh.org/blog/2018/07/postgresql-listen-notify/
    await conn.execute(
        f'''
        BEGIN;
        CREATE OR REPLACE FUNCTION notify_page_change ()
        RETURNS TRIGGER
        language plpgsql
        as $$
        declare
        channel text := TG_ARGV[0];
        BEGIN
        PERFORM (
            select pg_notify(channel, 'payload')
        );
        RETURN NULL;
        END;
        $$;
        DROP TRIGGER IF EXISTS notify_page_change ON page;
        CREATE TRIGGER notify_page_change
                AFTER INSERT OR UPDATE OR DELETE
                    ON page
            FOR EACH ROW
            EXECUTE PROCEDURE notify_page_change('{PAGE_CHANNEL}');
        COMMIT;
    '''
    )

    # Add page fixtures to have something interesting in the database
    await conn.executemany(
        '''
        INSERT INTO page(url, period, regex) VALUES($1, $2, $3)
        ON CONFLICT DO NOTHING
    ''',
        [
            ('https://httpbin.org/get', timedelta(minutes=5), r'Agent.*httpx'),
            ('https://google.com', timedelta(minutes=10), 'evil'),
        ],
    )


async def init_report_table(conn):
    """Initialize `report` table (idempotent)"""

    await conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS report(
            reportid serial PRIMARY KEY,
            pageid integer NOT NULL REFERENCES page ON DELETE CASCADE,
            elapsed interval NOT NULL,
            statuscode int NOT NULL,
            sent timestamp NOT NULL,
            found boolean
        )
    '''
    )


async def fetch_pages(conn) -> List[Page]:
    await init_page_table(conn)
    pages = [
        Page(
            row['pageid'],
            row['url'],
            row['period'],
            re.compile(row['regex']) if row['regex'] else None,
        )
        for row in await conn.fetch('SELECT * FROM page')
    ]

    return pages


async def save_report(conn, r: Report):
    await conn.execute(
        '''
        INSERT INTO report(pageid, elapsed, statuscode, sent, found)
        VALUES($1, $2, $3, $4, $5)
    ''',
        r.pageid,
        r.elapsed,
        r.status_code,
        r.sent,
        r.found,
    )
    print(f'saved to db: {r}')
