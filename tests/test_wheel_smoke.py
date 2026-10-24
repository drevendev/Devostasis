"""Packaging admission must reject wheels that source-tree tests could conceal."""

import importlib.util
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("wheel_smoke", Path(__file__).parents[1] / "scripts/wheel_smoke.py")
wheel_smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wheel_smoke)


def make_wheel(tmp_path, *, dependency=None, entry="devostasis.cli:main", missing=None, version="1.2.3"):
    info = "devostasis-1.2.3.dist-info"
    metadata = f"Metadata-Version: 2.4\nName: devostasis\nVersion: {version}\n"
    if dependency:
        metadata += f"Requires-Dist: {dependency}\n"
    members = {f"{info}/METADATA": metadata, f"{info}/WHEEL": "Wheel-Version: 1.0\n",
               f"{info}/RECORD": "", f"{info}/entry_points.txt": f"[console_scripts]\ndevostasis = {entry}\n",
               "devostasis/__init__.py": "", "devostasis/__main__.py": "", "devostasis/cli.py": ""}
    if missing:
        del members[missing]
    wheel = tmp_path / "devostasis-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return wheel


@pytest.mark.parametrize("dependency", [None, 'pytest>=8; extra == "dev"', "pytest>=8; extra == 'dev'"])
def test_accepts_empty_runtime_dependencies_and_simple_dev_extra(tmp_path, dependency):
    wheel_smoke.inspect_wheel(make_wheel(tmp_path, dependency=dependency), "1.2.3")


@pytest.mark.parametrize("dependency", [
    "requests>=2", 'requests; python_version < "99"',
    'requests; extra == "dev" or python_version < "99"',
    'requests; extra == "dev" and python_version < "99"', 'requests; extra != "dev"',
])
def test_refuses_runtime_or_unproven_complex_dependencies(tmp_path, dependency):
    with pytest.raises(ValueError, match="not provably extra-only"):
        wheel_smoke.inspect_wheel(make_wheel(tmp_path, dependency=dependency), "1.2.3")


def test_refuses_wrong_version(tmp_path):
    with pytest.raises(ValueError, match="version mismatch"):
        wheel_smoke.inspect_wheel(make_wheel(tmp_path, version="9.9.9"), "1.2.3")


def test_refuses_missing_cli(tmp_path):
    with pytest.raises(ValueError, match="missing wheel member"):
        wheel_smoke.inspect_wheel(make_wheel(tmp_path, missing="devostasis/cli.py"), "1.2.3")


def test_refuses_wrong_entry_point(tmp_path):
    with pytest.raises(ValueError, match="console entry point"):
        wheel_smoke.inspect_wheel(make_wheel(tmp_path, entry="unrelated:main"), "1.2.3")


def test_negative_controls_damage_the_actual_wheel(tmp_path):
    wheel = make_wheel(tmp_path)
    assert wheel_smoke.negative_controls(wheel, "1.2.3", tmp_path) == [
        "missing-cli", "wrong-version", "runtime-dependency", "extra-or-bypass",
    ]
    wheel_smoke.inspect_wheel(wheel, "1.2.3")
