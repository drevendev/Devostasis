"""Build and exercise the distribution without importing the source checkout."""

from __future__ import annotations

import argparse
import configparser
from email.parser import BytesParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def inspect_wheel(wheel: Path, expected_version: str) -> None:
    """Refuse incomplete/version-drifted wheels and unproven runtime dependencies."""
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate wheel members")
        metadata_paths = [p for p in names if p.endswith(".dist-info/METADATA")]
        require(len(metadata_paths) == 1, "expected one distribution METADATA")
        metadata_path = metadata_paths[0]
        info = metadata_path.rsplit("/", 1)[0]
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
        require(metadata.get("Name", "").lower() == "devostasis", "wrong distribution name")
        require(metadata.get_all("Version") == [expected_version], "wheel/source version mismatch")
        for requirement in metadata.get_all("Requires-Dist", []):
            distribution, separator, marker = requirement.partition(";")
            # Only the simple optional-extra form emitted by this project is
            # proven safe. An `or python_version ...` must not hide a runtime dep.
            require(bool(separator and distribution.strip() and re.fullmatch(
                r"\s*extra\s*==\s*(?:\"[A-Za-z0-9_.-]+\"|'[A-Za-z0-9_.-]+')\s*", marker
            )), f"dependency is not provably extra-only: {requirement}")
        for member in ("devostasis/__init__.py", "devostasis/cli.py", "devostasis/__main__.py",
                       f"{info}/WHEEL", f"{info}/RECORD", f"{info}/entry_points.txt"):
            require(member in names, f"missing wheel member: {member}")
        entry_points = configparser.ConfigParser(interpolation=None)
        entry_points.read_string(archive.read(f"{info}/entry_points.txt").decode("utf-8"))
        require(entry_points.get("console_scripts", "devostasis", fallback="") == "devostasis.cli:main",
                "missing or incorrect console entry point")


def negative_controls(wheel: Path, expected_version: str, directory: Path) -> list[str]:
    """Corrupt the actual built wheel; source imports must never rescue it."""
    cases = []
    with zipfile.ZipFile(wheel) as source:
        members = {p: source.read(p) for p in source.namelist()}
    metadata_path = next(p for p in members if p.endswith(".dist-info/METADATA"))
    for label in ("missing-cli", "wrong-version", "runtime-dependency", "extra-or-bypass"):
        damaged = dict(members)
        if label == "missing-cli":
            del damaged["devostasis/cli.py"]
        elif label == "wrong-version":
            damaged[metadata_path] = re.sub(
                rb"(?m)^Version: [^\r\n]+", b"Version: 0.0.0+invalid", damaged[metadata_path]
            )
        else:
            dependency = ("Requires-Dist: wheel-smoke-unexpected\n" if label == "runtime-dependency"
                          else 'Requires-Dist: wheel-smoke-unexpected; extra == "dev" or python_version < "99"\n')
            # Insert a new header before the metadata body.
            damaged[metadata_path] = dependency.encode() + damaged[metadata_path]
        path = directory / f"{label}.whl"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in damaged.items():
                archive.writestr(name, data)
        try:
            inspect_wheel(path, expected_version)
        except ValueError:
            cases.append(label)
        else:
            raise ValueError(f"negative control unexpectedly accepted: {label}")
    return cases


def run(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 120) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {command}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def smoke(source: Path, scratch_root: Path | None = None) -> dict[str, object]:
    project = tomllib.loads((source / "pyproject.toml").read_text("utf-8"))["project"]
    version = project["version"]
    require(project.get("dependencies") == [], "source declares runtime dependencies")
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    with tempfile.TemporaryDirectory(prefix="devostasis-wheel-", dir=scratch_root) as temporary:
        root = Path(temporary).resolve()
        require(not root.is_relative_to(source), "smoke directory must be outside the checkout")
        wheels = root / "dist"
        run([sys.executable, "-I", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(source)],
            cwd=root, env=env, timeout=240)
        built = list(wheels.glob("*.whl"))
        require(len(built) == 1, "expected exactly one built wheel")
        inspect_wheel(built[0], version)
        controls = negative_controls(built[0], version, root)
        venv = root / "venv"
        run([sys.executable, "-I", "-m", "venv", str(venv)], cwd=root, env=env)
        executable_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        python = executable_dir / ("python.exe" if os.name == "nt" else "python")
        cli = executable_dir / ("devostasis.exe" if os.name == "nt" else "devostasis")
        run([str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps", str(built[0])], cwd=root, env=env)
        outside = root / "outside"
        outside.mkdir()
        fixtures = outside / "fixtures"
        fixtures.mkdir()
        shutil.copy2(source / "examples/observations.json", fixtures / "observations.json")
        for name in ("sample-bundle", "work/bundle", "code/bundle"):
            shutil.copytree(source / "examples" / name, fixtures / name)
        shutil.copy2(source / "examples/code/packet.json", fixtures / "code/packet.json")
        # Inspect the actual isolated interpreter, not a source-tree import.
        check = """import importlib.metadata as m, json, pathlib, sys, devostasis
d = m.distribution('devostasis')
assert d.version == sys.argv[1] == devostasis.__version__
assert pathlib.Path(devostasis.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
print(json.dumps({'version': d.version, 'import': 'fresh-venv'}))
"""
        installed = json.loads(run([str(python), "-I", "-c", check, version], cwd=outside, env=env))
        require(run([str(cli), "--version"], cwd=outside, env=env).strip() == f"devostasis {version}", "CLI version mismatch")
        run([str(cli), "--help"], cwd=outside, env=env)
        commands = [
            ["verify", "--bundle", str(fixtures / "sample-bundle")],
            ["work", "verify", "--bundle", str(fixtures / "work/bundle")],
            ["work", "replay", "--bundle", str(fixtures / "work/bundle")],
            ["code", "verify", "--bundle", str(fixtures / "code/bundle")],
            ["code", "verify-packet", "--bundle", str(fixtures / "code/bundle"), "--packet", str(fixtures / "code/packet.json")],
            ["build", "--observations", str(fixtures / "observations.json"), "--store", str(outside / "store"),
             "--planning", "milestones", "--debt-label", "type:refactor", "--debt-mapping-version", "example-1"],
            ["verify", "--bundle", str(outside / "store/projects/github.com/acme/widget/latest")],
        ]
        for command in commands:
            run([str(cli), *command], cwd=outside, env=env)
        return {"wheel": built[0].name, "installed": installed, "negative_controls": controls,
                "offline_commands": len(commands), "platform": sys.platform, "python": sys.version.split()[0]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-root", type=Path, help="existing directory outside the source checkout")
    args = parser.parse_args()
    try:
        print(json.dumps(smoke(Path(__file__).resolve().parents[1], args.scratch_root), indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        print(f"wheel smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
