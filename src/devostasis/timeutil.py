"""UTC timestamp helpers. Every persisted timestamp is ``YYYY-MM-DDTHH:MM:SSZ``.

Durations that enter a classifier are exact rationals in seconds
(PV-FLOW-MERGE-LATENCY-001): fractional seconds of an RFC 3339 timestamp are
kept as exact decimal fractions, never rounded through binary floats.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from fractions import Fraction

UTC = timezone.utc
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

_EXACT_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})[Tt ](\d{2}:\d{2}:\d{2})(\.\d+)?\s*([Zz]|[+-]\d{2}:?\d{2})?$")


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


def exact_epoch_seconds(value: str) -> Fraction:
    """Seconds since the Unix epoch as an exact rational; fractional digits are kept exactly."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"timestamp expected, got {value!r}")
    match = _EXACT_TS.match(value.strip())
    if not match:
        raise ValueError(f"unsupported timestamp {value!r}")
    date, clock, fraction, zone = match.groups()
    if zone is None or zone in ("Z", "z"):
        offset = "+00:00"
    elif ":" in zone:
        offset = zone
    else:
        offset = zone[:3] + ":" + zone[3:]
    whole = datetime.fromisoformat(f"{date}T{clock}{offset}")
    delta = whole - EPOCH
    seconds = Fraction(delta.days * 86400 + delta.seconds)
    if fraction:
        digits = fraction[1:]
        seconds += Fraction(int(digits), 10 ** len(digits))
    return seconds


def exact_seconds_between(start: str, end: str) -> Fraction:
    """Exact non-negative duration in seconds between two timestamps."""
    diff = exact_epoch_seconds(end) - exact_epoch_seconds(start)
    return diff if diff > 0 else Fraction(0)


def median_fraction(values: list[Fraction]) -> Fraction:
    """Exact median: the middle value, or the arithmetic mean of the two middle values."""
    if not values:
        raise ValueError("median of an empty sample")
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def duration_text(seconds: Fraction | int) -> str:
    """Deterministic human rendering of a duration in seconds (whole units only)."""
    whole = int(Fraction(seconds))
    if whole < 0:
        whole = 0
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def utc_day(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d")


def compact_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
