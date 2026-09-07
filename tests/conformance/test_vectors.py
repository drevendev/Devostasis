"""Every conformance vector in the corpus, executed as an ordinary test (target B1).

The corpus under ``tests/vectors`` is the executable half of
``docs/spec/conformance.md``: a case written there as a vector is proved here,
by the same runner that will execute the vectors of ``PV-TEST-001`` when they
arrive. The documented examples under ``examples/vectors`` run too, so the
format shown in the specification cannot drift from the format the runner
accepts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devostasis import vectors

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "tests" / "vectors"
EXAMPLES = ROOT / "examples" / "vectors"

ALL = vectors.load([CORPUS, EXAMPLES])


def test_the_corpus_is_not_empty():
    """An empty corpus would make every case below vacuously true."""
    assert ALL, "no conformance vectors were loaded"
    assert any(vector.path.replace("\\", "/").startswith(str(CORPUS).replace("\\", "/")) for vector in ALL)


@pytest.mark.parametrize("vector", ALL, ids=lambda vector: vector.case)
def test_conformance_vector(vector):
    result = vectors.run(vector)
    assert result.ok, "\n".join([f"{vector.case}: {vector.title}"] + result.failures)


def test_every_kind_the_format_declares_is_exercised_by_the_corpus():
    """A kind nothing exercises is a promise, not a proof."""
    assert {vector.kind for vector in ALL} == set(vectors.KINDS)


def test_every_envelope_in_the_corpus_is_one_the_published_schema_accepts():
    """The runner and the published schema must accept the same evidence.

    Only the key sets are checked here: the runtime carries no JSON Schema
    validator, so this is the guard that a vector the runner runs is not a
    vector the schema beside it declares invalid.
    """
    from devostasis import canonical

    envelope = canonical.load_file(ROOT / "schemas" / "conformance-vector.schema.json")["$defs"]["envelope"]
    required, allowed = set(envelope["required"]), set(envelope["properties"])
    for vector in ALL:
        if vector.kind != "vital":
            continue
        for stated in vector.given["observations"]:
            keys = set(stated)
            assert required <= keys, f"{vector.case}: envelope is missing {sorted(required - keys)}"
            assert keys <= allowed, f"{vector.case}: envelope states {sorted(keys - allowed)}, which the schema does not declare"
