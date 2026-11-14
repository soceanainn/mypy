"""Benchmark event-style unions with hundreds of nominal classes.

Run from a mypy checkout, using the same Python for both versions:

    python misc/benchmark_large_union.py --sizes 100 300 600
    python misc/benchmark_large_union.py --mypy-dir /path/to/baseline

Each sample starts a fresh process and disables incremental checking, including
the cost of checking typeshed. No third-party event framework is required.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def event_source(size: int, branches: int, scenario: str) -> str:
    classes = "\n".join(f"class Event{i}:\n    value: int\n" for i in range(size))
    members = ", ".join(f"Event{i}" for i in range(size))
    source = f"from typing import Union\n{classes}\nEvent = Union[{members}]\n"
    source += "\ndef check(event: Event) -> int:\n"
    if scenario == "narrow":
        for i in range(min(branches, size)):
            source += f"    if isinstance(event, Event{i}):\n        return event.value\n"
    elif scenario == "truthy":
        source += "    if event:\n        return event.value\n"
    elif scenario == "assign":
        for i in range(100):
            source += f"    x{i}: Event = Event{size - 1 - i % size}()\n"
    return source + "    return event.value\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mypy-dir", type=Path, default=Path.cwd())
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 300, 600])
    parser.add_argument("--branches", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--scenario", choices=["narrow", "truthy", "assign"], default="narrow")
    args = parser.parse_args()
    if min(args.sizes) < 1 or args.repeat < 1 or args.branches < 0:
        parser.error("sizes and repeat must be positive; branches must be nonnegative")

    with tempfile.TemporaryDirectory(prefix="mypy-large-union-") as temp:
        root = Path(temp)
        for size in args.sizes:
            source = root / "events.py"
            source.write_text(event_source(size, args.branches, args.scenario), encoding="utf-8")
            samples = []
            for _ in range(args.repeat):
                start = time.perf_counter()
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "mypy",
                        "--no-incremental",
                        "--config-file=",
                        f"--cache-dir={root / 'cache'}",
                        str(source),
                    ],
                    cwd=args.mypy_dir,
                    capture_output=True,
                    text=True,
                )
                if result.returncode:
                    sys.exit(result.stdout + result.stderr)
                samples.append(time.perf_counter() - start)
            print(
                f"{args.scenario:6} {size:4} members: median {statistics.median(samples):.3f}s "
                f"(samples: {', '.join(f'{sample:.3f}' for sample in samples)})",
                flush=True,
            )


if __name__ == "__main__":
    main()
