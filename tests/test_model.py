from datetime import datetime

import pytest

from sitewatch.model import Report, ValidationError, ParseError


@pytest.mark.parametrize('found', [None, True, False])
def test_report_model(snapshot, found):
    r = Report(
        pageid=42,
        sent=datetime(2020, 1, 1, 1, 1, 1),
        elapsed=60.0,
        status_code=200,
        found=found,
    )
    b = r.tobytes()
    snapshot.assert_match(b)
    assert Report.frombytes(b) == r


@pytest.mark.parametrize(
    'raw',
    [
        b'',
        b'{',
        b'{"pageid": 42',
    ],
)
def test_report_model_parsing(snapshot, raw):
    try:
        Report.frombytes(raw)
    except ParseError as e:
        index = e.messages()[0].start_position.char_index
        snapshot.assert_match({'at char': index, 'message': str(e)})


@pytest.mark.parametrize(
    'raw',
    [
        b'{"pageid": 42, "sent": "broken-date", "elapsed": 60.0, "status_code": 200, "found": true}',
        b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": "broken-duration", "status_code": 200, "found": true}',
        b'{}',
    ],
)
def test_report_model_validation(snapshot, raw):
    try:
        Report.frombytes(raw)
    except ValidationError as e:
        snapshot.assert_match(dict(e))
