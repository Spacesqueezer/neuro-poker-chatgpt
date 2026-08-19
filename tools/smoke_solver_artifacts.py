import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import argparse
import json
from pathlib import Path

from poker.solver import (
	RestrictedSolverPolicy,
	StrategyLookup,
	evaluate_restricted_policy,
	load_strategy_export,
)
from tools.benchmark_mccfr import BENCHMARK_SCENARIOS, create_benchmark_game
from tools.export_mccfr_strategy import export_strategy


SMOKE_REPORT_VERSION = 1
DEFAULT_SCENARIOS = tuple(BENCHMARK_SCENARIOS)


def run_smoke(
	output_dir,
	iterations=10,
	seed=42,
	scenarios=DEFAULT_SCENARIOS,
):
	if iterations <= 0:
		raise ValueError("iterations must be positive")

	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	results = []
	for scenario in scenarios:
		if scenario not in BENCHMARK_SCENARIOS:
			raise ValueError(
				f"unknown benchmark scenario: {scenario}"
			)

		strategy_filename = f"{scenario}_strategy.json"
		strategy_path = output_dir / strategy_filename
		exported = export_strategy(
			iterations,
			seed,
			scenario,
			strategy_path,
		)
		reloaded = load_strategy_export(strategy_path)

		if reloaded != exported:
			raise RuntimeError(
				f"strategy artifact round trip mismatch: {scenario}"
			)

		game = create_benchmark_game(scenario)
		policy = RestrictedSolverPolicy(
			StrategyLookup(reloaded)
		)
		evaluation = evaluate_restricted_policy(
			game,
			policy,
		)

		results.append({
			"scenario": scenario,
			"starting_stacks": list(game.starting_stacks),
			"strategy_file": strategy_filename,
			"artifact_round_trip": True,
			"information_set_count": reloaded[
				"information_set_count"
			],
			"evaluation": evaluation,
		})

	report = {
		"smoke_report_version": SMOKE_REPORT_VERSION,
		"iterations": iterations,
		"seed": seed,
		"scenarios": results,
	}

	report_path = output_dir / "smoke_report.json"
	report_path.write_text(
		json.dumps(
			report,
			indent=2,
			sort_keys=True,
		) + "\n",
		encoding="utf-8",
	)

	return report


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--output-dir",
		default="artifacts/solver_smoke",
	)
	parser.add_argument("--iterations", type=int, default=10)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument(
		"--scenarios",
		nargs="+",
		choices=tuple(BENCHMARK_SCENARIOS),
		default=list(DEFAULT_SCENARIOS),
	)
	args = parser.parse_args()

	report = run_smoke(
		args.output_dir,
		iterations=args.iterations,
		seed=args.seed,
		scenarios=tuple(args.scenarios),
	)

	print(
		json.dumps(
			report,
			indent=2,
			sort_keys=True,
		)
	)


if __name__ == "__main__":
	main()
