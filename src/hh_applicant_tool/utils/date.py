from __future__ import annotations

import re
from datetime import datetime
from typing import Any

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
API_DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\Z")


def parse_api_datetime(dt: str) -> datetime:
    if not API_DATETIME_RE.fullmatch(dt):
        raise ValueError(f"time data {dt!r} does not match format {DATETIME_FORMAT!r}")
    return datetime.strptime(dt, DATETIME_FORMAT)


def try_parse_datetime(dt: Any) -> datetime | Any:
    for parse in (datetime.fromisoformat, parse_api_datetime):
        try:
            return parse(dt)
        except (ValueError, TypeError):
            pass
    return dt
