# Installed-wheel verification

Source tests and an editable installation do not prove that the distribution
contains a working CLI. From a Python 3.12+ checkout with pip available, run:

```bash
python scripts/wheel_smoke.py
```

The gate builds one wheel from this checkout; build isolation can download the
declared setuptools build dependency. It checks the source/metadata version,
required package members and console entry point, and refuses dependencies that
are not provably optional extras. Complex dependency markers fail closed.

It installs only that wheel with `--no-index --no-deps` in a fresh temporary venv,
removes inherited Python import paths, and runs outside the checkout. All example
inputs are copied there. Isolated import/version checks, CLI help/version, core,
work and code example verification/replay, and an offline fixture build must pass.
Four corrupted copies of the built wheel must fail admission: missing CLI, wrong
version, runtime dependency, and an optional-extra OR bypass. No corrupted wheel
is installed. The installed runtime smoke performs no network collection.

Every subprocess has a timeout; CI additionally limits the job to ten minutes.
Scratch files are removed on exit. Use `--scratch-root <existing-directory>` to
select a temporary-files location outside the checkout. A successful run prints
JSON with the wheel, environment and checks; any failed command exits nonzero.

The separate CI job targets **Ubuntu/Python 3.12** at the exact PR head (or push
SHA), alongside the existing source-test matrix. Windows can run the same script;
only a recorded successful execution qualifies that version/platform. macOS,
other wheel-consumer combinations, privileged path behavior, PyPI publication
and release acceptance remain unqualified by this gate. The current 0.6.0
checkout is an unreleased candidate; this command does not publish it.
