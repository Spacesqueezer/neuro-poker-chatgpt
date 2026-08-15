import argparse
import json

from poker.solver import (
	load_strategy_export,
	load_teacher_record_export,
	validate_teacher_record_compatibility,
)
from tools.benchmark_mccfr import create_benchmark_game


def validate_teacher_files(teacher_path, strategy_path):
	teacher = load_teacher_record_export(teacher_path)
	strategy = load_strategy_export(strategy_path)
	scenario = strategy["benchmark"].get("scenario")
	if not isinstance(scenario, str) or not scenario:
		raise ValueError(
			"strategy artifact benchmark scenario is required"
		)

	game = create_benchmark_game(scenario)
	validate_teacher_record_compatibility(
		teacher,
		strategy,
		game,
	)

	return {
		"status": "VALID",
		"teacher": str(teacher_path),
		"strategy": str(strategy_path),
		"scenario": scenario,
		"record_count": teacher["record_count"],
		"chance_space_identity": strategy["benchmark"][
			"chance_space"
		]["identity"],
	}


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--teacher", required=True)
	parser.add_argument("--strategy", required=True)
	args = parser.parse_args()

	print(
		json.dumps(
			validate_teacher_files(
				args.teacher,
				args.strategy,
			),
			indent=2,
			sort_keys=True,
		)
	)


if __name__ == "__main__":
	main()
