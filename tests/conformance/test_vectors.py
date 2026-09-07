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
