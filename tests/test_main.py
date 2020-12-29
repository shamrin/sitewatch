from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import re
from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager
import logging

import pytest
import trio
import trio.testing

from sitewatch.model import Report, Page
import sitewatch
from sitewatch import watch_page, watch_pages, watch_reports
from sitewatch import db
from sitewatch import kafka


MINUTES = 1
PAGE = Page(42, 'example.com', timedelta(minutes=MINUTES), re.compile(r''))
REPORT = Report(
    pageid=42,
    sent=datetime(2020, 1, 1, 1, 1, 1),
    elapsed=60.0,
    status_code=200,
    found=True,
)


async def test_watch_page(monkeypatch, snapshot, autojump_clock):
    """Test periodic page checking"""

    async def mock_check_page(_, page):
        snapshot.assert_match(trio.current_time())
        assert page == PAGE
        return REPORT

    monkeypatch.setattr(sitewatch, 'check_page', mock_check_page)

    producer = MagicMock()
    producer.send_and_wait = AsyncMock()

    with trio.move_on_after(MINUTES * 60 * 3 - 0.1):
        await watch_page(producer, PAGE)

    assert producer.send_and_wait.call_count == 3


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
    monkeypatch.setattr(sitewatch, 'watch_page', watch_page := AsyncMock())

    # no pages should result in no watch_page() calls
    fetch_pages.return_value = []
    nursery.start_soon(watch_pages)
    await trio.testing.wait_all_tasks_blocked()
    assert fetch_pages.await_count == 1
    watch_page.assert_not_awaited()

    # notification should result in another fetch_pages()
    fetch_pages.return_value = [PAGE, PAGE, PAGE]
    started.set()
    await trio.testing.wait_all_tasks_blocked()
    assert fetch_pages.await_count == 2
    # 3 pages should result in 3 watch_page() calls
    assert watch_page.await_count == 3
    assert all(args.args[1] == PAGE for args in watch_page.await_args_list)


@pytest.mark.parametrize(
    'raw,expected_ok,expected_out',
    [
        (b'{', False, r'parse error'),
        (b'', False, r'parse error'),
        (b'{}', False, r'validation error'),
        (
            b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": true}',
            True,
            r'saved to db',
        ),
    ],
)
async def test_watch_reports(
    monkeypatch, caplog, snapshot, raw, expected_ok, expected_out
):
    @asynccontextmanager
    async def consumer():
        async def messages():
            record = MagicMock()
            record.value = raw
            record.offset = 123
            yield record

        yield messages()

    monkeypatch.setattr(db, 'init_report_table', AsyncMock())
    monkeypatch.setattr(db, 'connect', MagicMock(return_value=AsyncMock()))
    monkeypatch.setattr(kafka, 'open_consumer', MagicMock(return_value=consumer()))
    monkeypatch.setattr(db, 'save_report', save_report := AsyncMock())

    with caplog.at_level(logging.INFO):
        await watch_reports()

    if expected_ok:
        save_report.assert_awaited_once()
    else:
        save_report.assert_not_awaited()

    if expected_out:
        pattern = re.compile(f'{expected_out}[^$]*', re.MULTILINE)
        out = caplog.text
        m = pattern.search(out)
        assert m is not None, f'pattern {pattern!r} not found in {out!r}'
        snapshot.assert_match(m[0])
