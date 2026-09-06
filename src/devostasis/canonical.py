"""Canonical JSON serialization and content digests (``devostasis.canon.v1``).

Rules of the profile:

* UTF-8, object keys sorted by Unicode code point, no insignificant whitespace;
* only ``null``, booleans, integers, strings, arrays and objects are allowed;
* floats are rejected outright: ratios are stored as ``{"num": x, "den": y}``
  records and exact durations as ``{"numerator": n, "denominator": d}``
  records (PV-FLOW-MERGE-LATENCY-001), so two implementations can never
  disagree on number formatting;
* digests are ``sha256:<hex>`` over the canonical bytes.

A pretty-printed file and its canonical form have the same digest, because the
digest is always recomputed from the parsed content.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

CANONICAL_SERIALIZATION_VERSION = "devostasis.canon.v1"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented in the canonical profile."""


def _validate(value: Any, path: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        raise CanonicalizationError(
            f"float at {path} is not allowed in canonical artifacts; use integers or a num/den record"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"non-string object key at {path}: {key!r}")
            _validate(item, f"{path}.{key}")
        return
    raise CanonicalizationError(f"unsupported type {type(value).__name__} at {path}")


def validate(value: Any) -> None:
    """Raise ``CanonicalizationError`` if ``value`` is outside the profile."""
    _validate(value, "$")


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes of ``value``."""
    validate(value)
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_bytes(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def digest(value: Any) -> str:
    """Digest of the canonical form of ``value``."""
    return digest_bytes(canonical_bytes(value))


def pretty_json(value: Any) -> str:
    """Human-readable JSON with sorted keys; canonically equivalent to ``canonical_bytes``."""
    validate(value)
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def loads(text: str) -> Any:
    return json.loads(text)


def load_file(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_pretty(path: str | Path, value: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(pretty_json(value).encode("utf-8"))


def write_canonical(path: str | Path, value: Any) -> bytes:
    data = canonical_bytes(value)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return data


def ratio(num: int, den: int) -> dict[str, int]:
    """Exact rational record used wherever a ratio must be persisted."""
    return {"num": int(num), "den": int(den)}


def rational_record(value: Fraction | int) -> dict[str, int]:
    """Exact reduced rational record ``{"numerator": n, "denominator": d}`` (durations in seconds)."""
    fraction = Fraction(value)
    return {"numerator": fraction.numerator, "denominator": fraction.denominator}


def rational_parts(value: Any) -> tuple[int, int] | None:
    """``(numerator, denominator)`` of a rational record in either persisted shape, else ``None``."""
    if not isinstance(value, dict) or len(value) != 2:
        return None
    for num_key, den_key in (("num", "den"), ("numerator", "denominator")):
        if set(value) == {num_key, den_key}:
            num, den = value[num_key], value[den_key]
            if isinstance(num, int) and isinstance(den, int) and not isinstance(num, bool) and not isinstance(den, bool) and den > 0:
                return num, den
    return None


def rational_from_record(value: Any) -> Fraction | None:
    parts = rational_parts(value)
    if parts is None:
        return None
    return Fraction(parts[0], parts[1])


def ratio_text(record: Any, places: int = 2) -> str:
    """Deterministic decimal rendering of a rational record for human output."""
    parts = rational_parts(record)
    if parts is None:
        return "n/a"
    num, den = parts
    scale = 10**places
    scaled = (num * scale * 2 + den) // (den * 2)
    whole, frac = divmod(scaled, scale)
    return f"{whole}.{frac:0{places}d}"
