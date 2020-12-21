import pytest

from datetime import datetime, timedelta

from sitewatch.model import Report, ValidationError

@pytest.mark.parametrize('found', [None, True, False])
def test_report_model(snapshot, found):
    r = Report(pageid=42, sent=datetime(2020,1,1,1,1,1), elapsed=timedelta(minutes=1),status_code=200,found=found)
    b = r.tobytes()
    snapshot.assert_match(b)
    assert Report.frombytes(b) == r

@pytest.mark.parametrize('invalid_field,broken', [
    ('datetime', b'{"pageid": 42, "sent": "broken-date", "elapsed": 60.0, "status_code": 200, "found": true}'),
    ('duration', b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": "broken-duration", "status_code": 200, "found": true}'),
    ('json', b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": true'),
])
def test_report_model_broken(invalid_field, broken):
    with pytest.raises(ValidationError, match=fr'invalid {invalid_field}'):
        Report.frombytes(broken)
