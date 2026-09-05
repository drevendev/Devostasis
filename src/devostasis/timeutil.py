"""UTC timestamp helpers. Every persisted timestamp is ``YYYY-MM-DDTHH:MM:SSZ``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_ts(value: str) -> datetime:
    """Parse an RFC 3339 / ISO 8601 timestamp into an aware UTC datetime (second precision)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"timestamp expected, got {value!r}")
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(microsecond=0)


def format_ts(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).strftime(TS_FORMAT)


def normalize_ts(value: str | None) -> str | None:
    if value is None:
        return None
    return format_ts(parse_ts(value))


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def minus_days(value: datetime, days: int) -> datetime:
    return value - timedelta(days=days)


def age_days(reference: datetime, moment: datetime) -> int:
    """Whole days elapsed from ``moment`` to ``reference``; never negative."""
    seconds = (reference - moment).total_seconds()
    if seconds <= 0:
        return 0
    return int(seconds // 86400)


def hours_between(start: datetime, end: datetime) -> int:
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        return 0
    return int(seconds // 3600)


def utc_day(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d")


def compact_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
