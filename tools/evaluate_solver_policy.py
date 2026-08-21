import os
import sys

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
from tools.benchmark_mccfr import create_benchmark_game


def evaluate_strategy_file(strategy_path):
	payload = load_strategy_export(strategy_path)
	scenario = payload["benchmark"].get("scenario")
	if not isinstance(scenario, str) or not scenario:
		raise ValueError(
			"strategy artifact benchmark scenario is required"
		)

	game = create_benchmark_game(scenario)
	policy = RestrictedSolverPolicy(
		StrategyLookup(payload)
	)
	report = evaluate_restricted_policy(game, policy)

	return {
		"strategy": str(strategy_path),
		"scenario": scenario,
		"starting_stacks": list(game.starting_stacks),
		**report,
	}


def write_report(report, output):
	path = Path(output)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		json.dumps(
			report,
			indent=2,
			sort_keys=True,
		) + "\n",
		encoding="utf-8",
	)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--strategy", required=True)
	parser.add_argument("--output")
	args = parser.parse_args()

	report = evaluate_strategy_file(args.strategy)
	if args.output:
		write_report(report, args.output)

	print(
		json.dumps(
			report,
			indent=2,
			sort_keys=True,
		)
	)


if __name__ == "__main__":
	main()
