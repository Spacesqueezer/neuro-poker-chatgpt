"""Reproduce disputed labels on fixed public states; never train weights."""

import argparse
from pathlib import Path

from poker.learning.snapshot_diagnostics import audit


def main():
    import torch

    torch.set_num_threads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    audit(
        args.data,
        args.checkpoint,
        args.evaluation,
        args.output,
        samples=args.samples,
        repeats=args.repeats,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
