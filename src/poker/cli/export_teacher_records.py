import argparse
import json

from poker.cli.benchmark_mccfr import create_benchmark_game
from poker.solver import (
	build_teacher_export,
	load_strategy_export,
	write_teacher_export,
)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--strategy", required=True)
	parser.add_argument("--output", required=True)
	args = parser.parse_args()

	strategy_payload = load_strategy_export(args.strategy)
	scenario_name = strategy_payload["benchmark"]["scenario"]
	game = create_benchmark_game(scenario_name)

	teacher_payload = build_teacher_export(strategy_payload, game)
	write_teacher_export(teacher_payload, args.output)

	print(
		json.dumps(
			{
				"strategy": args.strategy,
				"output": args.output,
				"format_version": teacher_payload["format_version"],
				"record_count": teacher_payload["record_count"],
			},
			indent=2,
		)
	)


if __name__ == "__main__":
	main()
