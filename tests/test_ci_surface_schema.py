"""Published closed schemas are checked by a real Draft 2020-12 validator."""

from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource
import pytest

from devostasis import canonical

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FILES = ("ci-normalization.schema.json", "conformance-bridge.schema.json")


def validator(name):
    resources = [canonical.load_file(SCHEMAS / file) for file in FILES]
    registry = Registry().with_resources((r["$id"], Resource.from_contents(r)) for r in resources)
    return Draft202012Validator(canonical.load_file(SCHEMAS / name), registry=registry)


@pytest.mark.parametrize("name", FILES)
def test_ci_surface_schemas_are_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(canonical.load_file(SCHEMAS / name))


@pytest.mark.parametrize("name", ["conformance-surface.json", "ci-revisions.json"])
def test_published_bridge_schema_accepts_every_literal_case(name):
    document = canonical.load_file(ROOT / "tests" / "fixtures" / name)
    validator("conformance-bridge.schema.json").validate(document)


@pytest.mark.parametrize("change", ["lineage", "scenario", "step", "native", "extra", "check"])
def test_published_bridge_schema_refuses_unknown_native_and_operation_fields(change):
    document = canonical.load_file(ROOT / "tests/fixtures/ci-revisions.json")
    case = next(c for c in document["cases"] if c["case"] == "R26")
    document["cases"] = [deepcopy(case)]; case = document["cases"][0]
    step = case["given"]["variants"][0]["steps"][0]
    if change == "lineage": step["evidence"]["contract"] += "+future"
    elif change == "scenario": case["scenario"] += "+future"
    elif change == "step": step["history"] = "SYNTHETIC_PREDECESSOR"
    elif change == "native": step["evidence"]["parents"][0]["native"]["ignored"] = True
    elif change == "extra": case["given"]["ignored"] = True
    else: case["checks"][0]["ignored"] = True
    with pytest.raises(ValidationError):
        validator("conformance-bridge.schema.json").validate(document)
