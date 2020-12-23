from datetime import datetime, timedelta
import re
from unittest.mock import AsyncMock

import pytest
import trio
import trio.testing

from sitewatch.model import Report, Page
import sitewatch
from sitewatch import check_and_produce


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


async def test_check_and_produce(
    monkeypatch, snapshot, report, kafka_producer, autojump_clock
):
    """Test periodic page checking"""

    minutes = 1
    page = Page(42, 'example.com', timedelta(minutes=minutes), re.compile(r''))

    async def mock_check_page(_, page_to_check):
        snapshot.assert_match(trio.current_time())
        assert page_to_check == page
        return report

    monkeypatch.setattr(sitewatch, 'check_page', mock_check_page)

    with trio.move_on_after(minutes * 60 * 3 - 0.1):
        await check_and_produce(kafka_producer, page)

    assert kafka_producer.send_and_wait.call_count == 3
