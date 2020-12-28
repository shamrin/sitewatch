from typing import Optional
from dataclasses import dataclass
from datetime import timedelta
import json
import re

import typesystem
from typesystem import ValidationError, ParseError


@dataclass
class Page:
    """"Web page to periodically check"""

    id: int
    url: str
    period: timedelta
    regex: Optional[re.Pattern[str]]


class Report(typesystem.Schema):
    """Web page check result"""

    pageid = typesystem.Integer(minimum=0)
    sent = typesystem.DateTime()
    elapsed = typesystem.Float(minimum=0)
    status_code = typesystem.Integer()
    found = typesystem.Boolean(default=None, allow_null=True)

    def tobytes(self) -> bytes:
        """Serialize to JSON"""
        return json.dumps(dict(self)).encode('utf8')

    @classmethod
    def frombytes(cls, raw: bytes) -> 'Report':
        """Deserialize from JSON"""
        return typesystem.validate_json(raw, validator=Report)
