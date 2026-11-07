"""Copy fixed train/validation splits and generate an independent natural test."""

import argparse
from pathlib import Path

from poker.learning.snapshot_holdout import prepare_holdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-data", type=Path, action="append", default=[])
    parser.add_argument("--hands", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=201000)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    manifest = prepare_holdout(
        args.source,
        args.output,
        hands=args.hands,
        seed=args.seed,
        workers=args.workers,
        exclude=args.exclude_data,
        progress=lambda hands, rows: print(f"{hands} hands, {rows} test rows", flush=True),
    )
    print(manifest["samples"])


if __name__ == "__main__":
    main()
