# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['test_watch_page 1'] = 0.0

snapshots['test_watch_page 2'] = 60.0

snapshots['test_watch_page 3'] = 120.0

snapshots['test_watch_reports[-False-parse error] 1'] = '''parse error "No content." at char 0: b\'\'
'''

snapshots['test_watch_reports[{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": true}-True-consumed message] 1'] = '''consumed message with offset 123: b\'{"pageid": 42, "sent": "2020-01-01T01:01:01", "elapsed": 60.0, "status_code": 200, "found": true}\'
'''

snapshots['test_watch_reports[{-False-parse error] 1'] = '''parse error "Expecting property name enclosed in double quotes." at char 1: b\'{\'
'''

snapshots['test_watch_reports[{}-False-validation error] 1'] = '''validation error {\'pageid\': "The field \'pageid\' is required.", \'sent\': "The field \'sent\' is required.", \'elapsed\': "The field \'elapsed\' is required.", \'status_code\': "The field \'status_code\' is required."}: b\'{}\'
'''
