from unittest.mock import AsyncMock

import pytest

from sitewatch.db import listen


class MockDbConnection:
    remove_listener = AsyncMock()

    async def add_listener(self, channel, callback):
        callback('conn', 'pid', channel, 'payload')


@pytest.fixture
def db_connection():
    return MockDbConnection()


async def test_listen(db_connection):
    async with listen(db_connection, 'changes') as channel:
        async for payload in channel:
            assert payload == 'payload'
            break

    # assert that remove_listener has been called
    db_connection.remove_listener.assert_awaited_once()
    assert db_connection.remove_listener.await_args.args[0] == 'changes'
