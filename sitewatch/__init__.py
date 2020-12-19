import os
from typing import Optional
from dataclasses import dataclass
from datetime import timedelta, datetime
import asyncio

import httpx
import asyncpg

@dataclass
class Page:
    id: int
    url: str
    period: timedelta
    regex: str

@dataclass
class Report:
    page: Page
    sent: datetime
    elapsed: timedelta
    status_code: int
    found: Optional[bool] = None

async def connect_db():
    db = os.environ.get('DATABASE', '')
    assert db.startswith('postgres://')
    return await asyncpg.connect(db)

async def fetch_urls():
    conn = await connect_db()

    await conn.execute('''
        CREATE TABLE IF NOT EXISTS page(
            pageid serial PRIMARY KEY,
            url text NOT NULL,
            period interval NOT NULL,
            regex text
        )
    ''')

    await conn.executemany('''
        INSERT INTO page(pageid, url, period, regex) VALUES($1, $2, $3, $4)
        ON CONFLICT DO NOTHING
    ''', [(1, 'https://httpbin.org/get', timedelta(minutes=5), 'httpx'),
          (2, 'https://google.com', timedelta(minutes=1), None),
          (3, 'https://google.com', timedelta(seconds=10), 'evil')])

    pages = [
        Page(row['pageid'], row['url'], row['period'], row['regex'])
        for row in await conn.fetch('SELECT * FROM page')
    ]

    await conn.close()

    return pages

async def save_report(r: Report):
    conn = await connect_db()

    await conn.execute('''
        CREATE TABLE IF NOT EXISTS report(
            responseid serial PRIMARY KEY,
            pageid integer NOT NULL REFERENCES page,
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


async def check(page):
    sleep = page.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            now = datetime.now()
            r = await client.get(page.url)
            prefix = f'pageid:{page.id} url:{page.url} period:{page.period} regex:{page.regex!r}:'
            if page.regex is not None:
                print(prefix, 'OK' if page.regex in r.text else 'ERROR')
            report = Report(
                page = page,
                sent = now,
                elapsed = r.elapsed,
                status_code = r.status_code,
                found = None if page.regex is None else page.regex in r.text,
            )
            await save_report(report)
            print(prefix, f'waiting {sleep}s...')
            await asyncio.sleep(sleep)

async def main():
    print('starting up')

    pages = await fetch_urls()

    for page in pages:
        asyncio.create_task(check(page))

    # TODO: fix this
    await asyncio.sleep(1000)

def start():
    asyncio.run(main())
