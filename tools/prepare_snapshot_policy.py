"""Generate versioned imitation data; no neural training or player database."""

import argparse
import json
from pathlib import Path

from poker.learning.snapshot_dataset import SCENARIOS, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hands", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=71000)
    parser.add_argument("--equity-samples", type=int, default=128)
    parser.add_argument("--extra-train-hands", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--scenario", choices=SCENARIOS, default="standard-v1")
    args = parser.parse_args()
    result = prepare(
        args.output,
        hands=args.hands,
        seed=args.seed,
        equity_samples=args.equity_samples,
        extra_train_hands=args.extra_train_hands,
        workers=args.workers,
        scenario=args.scenario,
        progress=lambda count, rows: print(f"{count} hands; samples {rows}", flush=True),
    )
    print(json.dumps({k: result[k] for k in ("config", "samples", "rejections")}))


if __name__ == "__main__":
    main()
