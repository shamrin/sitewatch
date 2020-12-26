# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_report_model[False] 1'] = b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": false}'

snapshots['test_report_model[None] 1'] = b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": null}'

snapshots['test_report_model[True] 1'] = b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": true}'

snapshots['test_report_model_parsing[] 1'] = {
    'at char': 0,
    'message': 'No content.'
}

snapshots['test_report_model_parsing[{"pageid": 42] 1'] = {
    'at char': 13,
    'message': "Expecting ',' delimiter."
}

snapshots['test_report_model_parsing[{] 1'] = {
    'at char': 1,
    'message': 'Expecting property name enclosed in double quotes.'
}

snapshots['test_report_model_validation[{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": "broken-duration", "status_code": 200, "found": true}] 1'] = {
    'elapsed': 'Must be a number.'
}

snapshots['test_report_model_validation[{"pageid": 42, "sent": "broken-date", "elapsed": 60.0, "status_code": 200, "found": true}] 1'] = {
    'sent': 'Must be a valid datetime format.'
}

snapshots['test_report_model_validation[{}] 1'] = {
    'elapsed': "The field 'elapsed' is required.",
    'pageid': "The field 'pageid' is required.",
    'sent': "The field 'sent' is required.",
    'status_code': "The field 'status_code' is required."
}
