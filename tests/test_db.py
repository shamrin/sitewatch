import os
from unittest.mock import AsyncMock

import pytest
import trio
from testcontainers.postgres import PostgresContainer
import trio_asyncio

from sitewatch.db import listen
from sitewatch.db import connect

@pytest.fixture
async def db_connection(nursery):
    started = trio.Event()

    class MockDbConnection:
        remove_listener = AsyncMock()
        _add_listener_called = False

        async def add_listener(self, channel, callback):
            async def send_on_event(task_status):
                task_status.started()
                await started.wait()
                callback('conn', 'pid', channel, 'payload')

            await nursery.start(send_on_event)
            self._add_listener_called = True

    conn = MockDbConnection()
    return started, conn


# https://github.com/Scille/parsec-cloud/blob/b80cdb3922da9bf1614900885d8244b294cafd1c/tests/conftest.py#L260-L272
@pytest.fixture
async def asyncio_loop():
    # When a ^C happens, trio send a Cancelled exception to each running
    # coroutine. We must protect this one to avoid deadlock if it is cancelled
    # before another coroutine that uses trio-asyncio.
    with trio.CancelScope(shield=True):
        async with trio_asyncio.open_loop() as loop:
            yield loop


@pytest.fixture
async def connection(asyncio_loop, nursery):
    def run_db(send_to_trio, stopped):
        print('starting db')
        with PostgresContainer("postgres:12.5-alpine") as postgres:
            trio.from_thread.run(send_to_trio.send, postgres.get_connection_url())
            trio.from_thread.run(stopped.wait)
            print('stopping db')

    stopped = trio.Event()
    send_to_trio, receive_from_thread = trio.open_memory_channel(0)
    nursery.start_soon(trio.to_thread.run_sync, run_db, send_to_trio, stopped)
    url = await receive_from_thread.receive()
    os.environ['PG_SERVICE_URI'] = url.replace('+psycopg2','')
    async with connect() as conn:
        yield conn
    stopped.set()


async def test_connection(connection):
    for row in await connection.fetch('select version()'):
        print(f'1 {row["version"]=}')

async def test_connection2(connection):
    for row in await connection.fetch('select version()'):
        print(f'2 {row["version"]=}')


async def test_listen(db_connection):
    started, connection = db_connection

    assert not connection._add_listener_called

    async with listen(connection, 'changes') as changes:
        # confirm there is nothing to receive at the beginning
        assert connection._add_listener_called
        with pytest.raises(trio.WouldBlock):
            changes.receive_nowait()

        # start notification and confirm its receival
        started.set()
        assert await changes.receive() == 'payload'

    # assert that remove_listener has been called
    connection.remove_listener.assert_awaited_once()
    assert connection.remove_listener.await_args.args[0] == 'changes'
