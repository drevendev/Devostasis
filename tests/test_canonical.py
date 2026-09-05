import pytest

from devostasis import canonical


def test_canonical_bytes_sort_keys_and_strip_whitespace():
    assert canonical.canonical_bytes({"b": 1, "a": [1, {"z": None, "y": "x"}]}) == b'{"a":[1,{"y":"x","z":null}],"b":1}'


def test_floats_are_rejected():
    with pytest.raises(canonical.CanonicalizationError):
        canonical.canonical_bytes({"ratio": 0.25})


def test_pretty_and_canonical_share_a_digest():
    value = {"k": [3, 2, 1], "nested": {"b": True, "a": "ü"}}
    pretty = canonical.loads(canonical.pretty_json(value))
    assert canonical.digest(pretty) == canonical.digest(value)


def test_digest_is_stable_and_prefixed():
    assert canonical.digest({"a": 1}) == "sha256:" + canonical.sha256_hex(b'{"a":1}')


def test_ratio_records_render_deterministically():
    assert canonical.ratio_text(canonical.ratio(1, 4)) == "0.25"
    assert canonical.ratio_text(canonical.ratio(2, 3)) == "0.67"
    assert canonical.ratio_text(None) == "n/a"
