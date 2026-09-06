"""The published specification must not promise proof that does not exist (debt D-4).

`docs/spec/conformance.md` is the public claim about what is verified. Until
now the only thing keeping it true was someone reading it, and the research
process has already caught the specification describing behaviour the code had
moved past. A citation that no longer resolves is now a red build.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFORMANCE = ROOT / "docs" / "spec" / "conformance.md"
CITATION = re.compile(r"`(test_[a-z0-9_]*\*?)`")
DEFINITION = re.compile(r"^def (test_[a-z0-9_]+)", re.MULTILINE)


def _defined_tests() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "tests").rglob("*.py"):
        names.update(DEFINITION.findall(path.read_text(encoding="utf-8")))
    return names


def _cited_tests() -> set[str]:
    return set(CITATION.findall(CONFORMANCE.read_text(encoding="utf-8")))


def test_every_test_the_conformance_table_cites_exists():
    defined = _defined_tests()
    cited = _cited_tests()
    assert cited, "the conformance table cites no tests at all"
    missing = sorted(
        name
        for name in cited
        if not (any(other.startswith(name[:-1]) for other in defined) if name.endswith("*") else name in defined)
    )
    assert not missing, f"conformance.md cites tests that no longer exist: {missing}"


def test_the_specification_index_lists_every_specification_page():
    index = (ROOT / "docs" / "spec" / "README.md").read_text(encoding="utf-8")
    pages = {path.name for path in (ROOT / "docs" / "spec").glob("*.md")} - {"README.md"}
    missing = sorted(name for name in pages if f"]({name})" not in index)
    assert not missing, f"docs/spec/README.md does not link: {missing}"


def test_every_contract_identifier_the_code_declares_is_documented():
    """A version the runtime writes into a bundle must be findable in the specification."""
    from devostasis import contracts

    documented = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "docs" / "spec").glob("*.md"))
    documented += (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    values = {
        name: getattr(contracts, name)
        for name in dir(contracts)
        if name.isupper() and isinstance(getattr(contracts, name), str)
    }
    missing = sorted(f"{name}={value}" for name, value in values.items() if value not in documented)
    assert not missing, f"contract identifiers absent from docs/spec: {missing}"
