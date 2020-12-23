from unittest.mock import AsyncMock

import pytest
import trio

from sitewatch.db import listen


@pytest.fixture
async def send_connection(nursery):
    send = trio.Event()

    class MockDbConnection:
        remove_listener = AsyncMock()
        _add_listener_called = False

        async def add_listener(self, channel, callback):
            async def send_on_event(task_status):
                task_status.started()
                await send.wait()
                callback('conn', 'pid', channel, 'payload')

            await nursery.start(send_on_event)
            self._add_listener_called = True

    conn = MockDbConnection()
    return send, conn


async def test_listen(send_connection):
    send, connection = send_connection

    assert not connection._add_listener_called

    async with listen(connection, 'changes') as changes:
        # confirm there is nothing to receive at the beginning
        assert connection._add_listener_called
        with pytest.raises(trio.WouldBlock):
            changes.receive_nowait()

        # send notification and confirm its receival
        send.set()
        assert await changes.receive() == 'payload'

    # assert that remove_listener has been called
    connection.remove_listener.assert_awaited_once()
    assert connection.remove_listener.await_args.args[0] == 'changes'
