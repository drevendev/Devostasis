"""Run the exact published operation bridge from a source checkout, offline."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from surface_bridge import CONTRACT, execute, load_suite
from devostasis.vectors import load as load_vectors


def main():
    cases = load_suite()
    old = {v.case for v in load_vectors([ROOT / "tests/vectors"])}
    if old.intersection(c["case"] for c in cases): raise ValueError("duplicate permanent case across carriers")
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="devostasis-conformance-") as directory:
            execute(case, Path(directory))
        print(case["case"], "PASS")
    print(CONTRACT, len(cases), "passed")


if __name__ == "__main__":
    main()
