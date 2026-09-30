"""Run every test module in this directory.

    python tests/run_all.py

Each module is a plain script of asserts rather than a pytest suite, so the
project needs no test dependency on the Pi. They stub smbus2 and spidev, so they
run on a development machine with no hardware attached.
"""

import subprocess
import sys
from pathlib import Path

TESTS = sorted(p for p in Path(__file__).parent.glob("test_*.py"))
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    failures = []
    for test in TESTS:
        print(f"\n=== {test.name} " + "=" * (60 - len(test.name)))
        result = subprocess.run(
            [sys.executable, str(test)],
            cwd=ROOT,
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
        )
        if result.returncode != 0:
            failures.append(test.name)

    print("\n" + "=" * 68)
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print(f"All {len(TESTS)} test modules passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
