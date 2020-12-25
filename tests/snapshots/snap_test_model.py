# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import GenericRepr, Snapshot


snapshots = Snapshot()

snapshots['test_report_model[False] 1'] = b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": false}'

snapshots['test_report_model[None] 1'] = b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": null}'

snapshots['test_report_model[True] 1'] = b'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": true}'
