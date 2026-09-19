"""Single place for 'now'. datetime.utcnow() is deprecated; we keep naive-UTC
values so SQLite and Postgres behave the same."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
