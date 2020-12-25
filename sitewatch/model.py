from typing import Optional
from dataclasses import dataclass, asdict
from datetime import timedelta, datetime
import json
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
        d = asdict(self)
        d['elapsed'] = d['elapsed'].total_seconds()
        d['sent'] = d['sent'].isoformat()
        return json.dumps(d).encode('utf8')

    @classmethod
    def frombytes(cls, raw: bytes) -> 'Report':
        """Deserialize"""
        try:
            d = json.loads(str(raw, 'utf8'))
        except json.JSONDecodeError:
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
