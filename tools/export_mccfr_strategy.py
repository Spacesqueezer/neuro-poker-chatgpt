import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import argparse
import json

from poker.solver import (
	ExternalSamplingMCCFR,
	build_strategy_export,
	write_strategy_export,
)
from tools.benchmark_mccfr import (
	BENCHMARK_SCENARIOS,
	create_benchmark_game,
)


BENCHMARK_VERSION = 2


def export_strategy(iterations, seed, scenario, output):
	if iterations <= 0:
		raise ValueError("iterations must be positive")

	game = create_benchmark_game(scenario)
	result = ExternalSamplingMCCFR(
		game,
		seed=seed,
	).train(iterations)
	payload = build_strategy_export(
		result,
		game,
		seed=seed,
		scenario=scenario,
		benchmark_version=BENCHMARK_VERSION,
	)
	write_strategy_export(payload, output)
	return payload


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--iterations", type=int, default=100)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument(
		"--scenario",
		choices=tuple(BENCHMARK_SCENARIOS),
		default="equal",
	)
	parser.add_argument("--output", required=True)
	args = parser.parse_args()

	payload = export_strategy(
		args.iterations,
		args.seed,
		args.scenario,
		args.output,
	)
	print(
		json.dumps(
			{
				"output": args.output,
				"format_version": payload["format_version"],
				"scenario": payload["benchmark"]["scenario"],
				"starting_stacks": payload["benchmark"][
					"starting_stacks"
				],
				"iterations": payload["iterations"],
				"information_set_count": payload[
					"information_set_count"
				],
			},
			indent=2,
		)
	)


if __name__ == "__main__":
	main()
