import os
from datetime import timedelta


def postgres_service() -> str:
    db = os.environ.get('PG_SERVICE_URI')
    assert db, 'PG_SERVICE_URI env var is missing'
    return db


async def init_page_table(pool):
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
