from typing import Optional
from dataclasses import dataclass
from datetime import timedelta, datetime
import orjson
import re


@dataclass
class Page:
    """"Web page to periodically check"""

    id: int
    url: str
    period: timedelta
    regex: Optional[re.Pattern[str]]


class ValidationError(Exception):
    """Error deserializing Report"""

    pass


def default(obj):
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    raise TypeError


@dataclass
class Report:
    """Web page check result"""

    pageid: int
    sent: datetime
    elapsed: timedelta
    status_code: int
    found: Optional[bool] = None

    def tobytes(self) -> bytes:
        """Serialize"""
        return orjson.dumps(self, default=default)

    @classmethod
    def frombytes(cls, raw: bytes) -> 'Report':
        """Deserialize"""
        try:
            d = orjson.loads(raw)
        except orjson.JSONDecodeError:
            raise ValidationError('invalid json')
        try:
            elapsed = timedelta(seconds=d['elapsed'])
        except TypeError:
            raise ValidationError('invalid duration')
        try:
            sent = datetime.fromisoformat(d['sent'])
        except ValueError:
            raise ValidationError('invalid datetime')

        return cls(
            pageid=d['pageid'],
            sent=sent,
            elapsed=elapsed,
            status_code=d['status_code'],
            found=d['found'],
        )
