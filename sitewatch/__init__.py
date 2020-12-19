import os
from dataclasses import dataclass
import asyncio

import httpx
import asyncpg
import datetime

@dataclass
class Check:
    url: str
    period: datetime.timedelta
    regex: str

async def fetch_urls():
    db = os.environ.get('DATABASE', '')
    assert db.startswith('postgres://')
    conn = await asyncpg.connect(db)

    await conn.execute('''
        CREATE TABLE IF NOT EXISTS urls(
            id serial PRIMARY KEY,
            url text UNIQUE,
            period interval,
            regex text
        )
    ''')

    await conn.executemany('''
        INSERT INTO urls(url, period, regex) VALUES($1, $2, $3)
        ON CONFLICT DO NOTHING
    ''', [('https://httpbin.org/get', datetime.timedelta(minutes=5), 'httpx'),
          ('https://google.com', datetime.timedelta(minutes=1), 'moved')])

    urls = [Check(r['url'], r['period'], r['regex']) for r in await conn.fetch('SELECT * FROM urls')]

    await conn.close()

    return urls

async def check(url):
    sleep = url.period.total_seconds()
    async with httpx.AsyncClient() as client:
        while True:
            r = await client.get(url.url)
            print(f'{url.url}:', 'OK' if url.regex in r.text else 'ERROR')
            print(f'{url.url}:', f'waiting {sleep}s...')
            await asyncio.sleep(sleep)

async def main():
    print('starting up')

    urls = await fetch_urls()

    for url in urls:
        asyncio.create_task(check(url))

    await asyncio.sleep(1000)

def start():
    asyncio.run(main())
