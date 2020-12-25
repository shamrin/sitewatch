from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import re
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

import pytest
import trio
import trio.testing

from sitewatch.model import Report, Page
import sitewatch
from sitewatch import check_and_produce, watch_pages
from sitewatch import db
from sitewatch import kafka


@pytest.fixture
def report():
    return Report(
        pageid=42,
        sent=datetime(2020, 1, 1, 1, 1, 1),
        elapsed=timedelta(minutes=1),
        status_code=200,
        found=True,
    )


class MockKafkaProducer:
    send_and_wait = AsyncMock()


@pytest.fixture
def kafka_producer():
    return MockKafkaProducer()


MINUTES = 1
PAGE = Page(42, 'example.com', timedelta(minutes=MINUTES), re.compile(r''))


async def test_check_and_produce(
    monkeypatch, snapshot, report, kafka_producer, autojump_clock
):
    """Test periodic page checking"""

    async def mock_check_page(_, page):
        snapshot.assert_match(trio.current_time())
        assert page == PAGE
        return report

    monkeypatch.setattr(sitewatch, 'check_page', mock_check_page)

    with trio.move_on_after(MINUTES * 60 * 3 - 0.1):
        await check_and_produce(kafka_producer, PAGE)

    assert kafka_producer.send_and_wait.call_count == 3


@pytest.fixture
async def db_listen(nursery):
    started = trio.Event()
    send_channel, receive_channel = trio.open_memory_channel(1)

    @asynccontextmanager
    async def listen(*args):
        async def send_on_event():
            await started.wait()
            send_channel.send_nowait('payload')

        nursery.start_soon(send_on_event)

        async with send_channel:
            yield receive_channel

    yield started, listen


async def test_watch_pages(nursery, monkeypatch, db_listen):
    """Test watch_pages() reaction to changes via db.listen()"""

    started, listen = db_listen

    monkeypatch.setattr(db, 'listen', listen)
    monkeypatch.setattr(db, 'init_page_table', AsyncMock())
    monkeypatch.setattr(db, 'connect', MagicMock(return_value=AsyncMock()))
    monkeypatch.setattr(db, 'fetch_pages', fetch_pages := AsyncMock())
    monkeypatch.setattr(kafka, 'open_producer', MagicMock(return_value=AsyncMock()))
    monkeypatch.setattr('sitewatch.check_and_produce', check_and_produce := AsyncMock())

    # no pages should result in no check_and_produce() calls
    fetch_pages.return_value = []
    nursery.start_soon(watch_pages)
    await trio.testing.wait_all_tasks_blocked()
    assert fetch_pages.await_count == 1
    check_and_produce.assert_not_awaited()

    # notification should result in another fetch_pages()
    fetch_pages.return_value = [PAGE, PAGE, PAGE]
    started.set()
    await trio.testing.wait_all_tasks_blocked()
    assert fetch_pages.await_count == 2
    # 3 pages should result in 3 check_and_produce() calls
    assert check_and_produce.await_count == 3
    assert all(args.args[1] == PAGE for args in check_and_produce.await_args_list)
