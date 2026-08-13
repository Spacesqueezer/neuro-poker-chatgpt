import argparse
import json

from poker.learning.generation import (
	DatasetGenerationConfig,
	LearningDatasetGenerator,
)


def main():
	parser = argparse.ArgumentParser(
		description="Generate a reproducible poker learning dataset.",
	)
	parser.add_argument("--output", required=True)
	parser.add_argument("--hands", type=int, default=10000)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--starting-stack", type=int, default=100)
	parser.add_argument("--validation-fraction", type=float, default=0.1)
	parser.add_argument(
		"--agents",
		nargs="+",
		default=["random", "calling_station", "nit"],
		choices=["random", "calling_station", "nit"],
	)
	args = parser.parse_args()

	config = DatasetGenerationConfig(
		hands=args.hands,
		seed=args.seed,
		starting_stack=args.starting_stack,
		validation_fraction=args.validation_fraction,
		agents=tuple(args.agents),
	)
	result = LearningDatasetGenerator().generate(
		args.output,
		config,
	)

	print(
		json.dumps(
			{
				"raw_path": str(result.raw_path),
				"train_path": str(result.train_path),
				"validation_path": str(result.validation_path),
				"manifest_path": str(result.manifest_path),
				"raw_samples": result.raw_samples,
				"train_samples": result.train_samples,
				"validation_samples": result.validation_samples,
				"arena_hands": result.arena_hands,
				"arena_failed_hands": result.arena_failed_hands,
			},
			indent=2,
		)
	)


if __name__ == "__main__":
	main()
