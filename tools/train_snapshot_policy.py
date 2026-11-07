"""Explicitly train, preflight or evaluate the new offline snapshot policy."""

import argparse
import json
from pathlib import Path

from poker.learning.snapshot_encoding import FEATURE_SETS
from poker.learning.snapshot_training import AUGMENTATIONS, OBJECTIVES, evaluate, preflight, train


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--evaluate", type=Path, metavar="CHECKPOINT")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--objective", choices=OBJECTIVES, default="legacy-v1")
    parser.add_argument("--augmentation", choices=AUGMENTATIONS, default="none")
    parser.add_argument("--features", choices=FEATURE_SETS, default="raw-v1")
    args = parser.parse_args()
    if args.preflight:
        result = preflight(args.data, feature_set=args.features)
    elif args.output is None:
        parser.error("--output is required for training or evaluation")
    elif args.evaluate:
        result = evaluate(args.data, args.evaluate, args.output, device=args.device)
    else:
        result = train(
            args.data,
            args.output,
            epochs=args.epochs,
            batch_size=args.batch_size,
            seed=args.seed,
            learning_rate=args.learning_rate,
            device=args.device,
            objective=args.objective,
            augmentation=args.augmentation,
            feature_set=args.features,
            progress=lambda metrics: print(json.dumps(metrics), flush=True),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
