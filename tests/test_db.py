from unittest.mock import MagicMock, AsyncMock, Mock

import trio
import trio.testing

from sitewatch.db import listen


def test_listen():
    class MockConnection:
        remove_listener = AsyncMock()

        async def add_listener(self, channel, callback):
            callback('conn', 'pid', channel, 'payload')

    async def run(conn):
        async with listen(conn, 'changes') as channel:
            with trio.move_on_after(1):
                async for payload in channel:
                    assert payload == 'payload'

    conn = MockConnection()
    clock = trio.testing.MockClock(autojump_threshold=0)
    trio.run(run, conn, clock=clock)

    # assert that remove_listener has been called
    conn.remove_listener.assert_awaited_once()
    assert len(conn.remove_listener.await_args) == 2
    assert conn.remove_listener.await_args.args[0] == 'changes'
