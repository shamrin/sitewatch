from datetime import datetime, timedelta
import re
from unittest.mock import MagicMock, AsyncMock

import trio
import trio.testing
import httpx

from sitewatch.model import Report, Page
import sitewatch
from sitewatch import check_and_produce

MOCK_REPORT = Report(
    pageid=42,
    sent=datetime(2020, 1, 1, 1, 1, 1),
    elapsed=timedelta(minutes=1),
    status_code=200,
    found=True,
)


def test_check_and_produce(monkeypatch, snapshot):
    """Test periodic page checking"""

    times = []
    period_minutes = 1

    class MockKafkaProducer:
        send_and_wait = AsyncMock()

    async def mock_check_page(*args):
        times.append(trio.current_time())
        return MOCK_REPORT

    monkeypatch.setattr(sitewatch, 'check_page', mock_check_page)

    monkeypatch.setattr(httpx, 'AsyncClient', MagicMock)

    async def cancel(fn, *arg):
        with trio.move_on_after(period_minutes * 60 * 3 - 0.1):
            await fn(*arg)

    page = Page(42, 'example.com', timedelta(minutes=period_minutes), re.compile(r''))

    clock = trio.testing.MockClock(autojump_threshold=0)
    trio.run(cancel, check_and_produce, MockKafkaProducer(), page, clock=clock)

    snapshot.assert_match(times)

    assert MockKafkaProducer.send_and_wait.call_count == 3
