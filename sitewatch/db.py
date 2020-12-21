"""Datatabase connection, tables init and main operations"""

import os
from datetime import timedelta
import re
from typing import List

import asyncpg

from .model import Report, Page


def postgres_service() -> str:
    db = os.environ.get('PG_SERVICE_URI')
    assert db, 'PG_SERVICE_URI env var is missing'
    return db


async def init_page_table(pool):
    """Initialize `page` table and add fixtures (idempotent)"""

    await pool.execute(
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

    # Add page fixtures to have something interesting in the database
    await pool.executemany(
        '''
        INSERT INTO page(url, period, regex) VALUES($1, $2, $3)
        ON CONFLICT DO NOTHING
    ''',
        [
            ('https://httpbin.org/get', timedelta(minutes=5), r'Agent.*httpx'),
            ('https://google.com', timedelta(minutes=10), 'evil'),
        ],
    )


async def init_report_table(pool):
    """Initialize `report` table (idempotent)"""

    await pool.execute(
        '''
        CREATE TABLE IF NOT EXISTS report(
            responseid serial PRIMARY KEY,
            pageid integer NOT NULL REFERENCES page ON DELETE CASCADE,
            elapsed interval NOT NULL,
            statuscode int NOT NULL,
            sent timestamp NOT NULL,
            found boolean
        )
    '''
    )


async def fetch_pages() -> List[Page]:
    async with asyncpg.create_pool(postgres_service()) as pool:
        await init_page_table(pool)
        pages = [
            Page(
                row['pageid'],
                row['url'],
                row['period'],
                re.compile(row['regex']) if row['regex'] else None,
            )
            for row in await pool.fetch('SELECT * FROM page')
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
