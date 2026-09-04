#!/usr/bin/env python
"""Single entry point for the reproducible NPSDM release."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "model"))

from npsdm import interpreter, settings  # noqa: E402


def main() -> int:
    """Parse the run mode, execute the model, and write the result tables."""
    parser = argparse.ArgumentParser(description="Run the NPSDM shared-setpoint model")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--smoke", action="store_true", help="Run 2 group-size cells with 3 repetitions"
    )
    group.add_argument(
        "--full", action="store_true", help="Run group sizes 3 through 10 with 300 repetitions"
    )
    args = parser.parse_args()

    if args.smoke:
        tag = "smoke"
        sizes = settings.SMOKE_GROUP_SIZES
        repetitions = settings.SMOKE_REPETITIONS
    else:
        tag = "full"
        sizes = settings.GROUP_SIZES
        repetitions = settings.REPETITIONS

    result = interpreter.run(sizes, repetitions)
    interpreter.write_outputs(result, tag)
    print(f"{tag}: {len(result['groups']):,} group-rule rows; {len(result['summary']):,} summary rows")
    print("Results written to outputs/results/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
