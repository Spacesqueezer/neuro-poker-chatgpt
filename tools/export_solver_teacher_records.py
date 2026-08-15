import argparse
import json

from poker.solver import (
	build_teacher_record_export,
	load_strategy_export,
	write_teacher_record_export,
)
from tools.benchmark_mccfr import create_benchmark_game


def export_teacher_records(strategy_path, output):
	payload = load_strategy_export(strategy_path)
	scenario = payload["benchmark"].get("scenario")
	if not isinstance(scenario, str) or not scenario:
		raise ValueError(
			"strategy artifact benchmark scenario is required"
		)

	game = create_benchmark_game(scenario)
	records = build_teacher_record_export(payload, game)
	write_teacher_record_export(records, output)
	return records


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--strategy", required=True)
	parser.add_argument("--output", required=True)
	args = parser.parse_args()

	report = export_teacher_records(
		args.strategy,
		args.output,
	)

	print(
		json.dumps(
			{
				"output": args.output,
				"format_version": report["format_version"],
				"scenario": report["source_strategy"][
					"benchmark"
				]["scenario"],
				"record_count": report["record_count"],
				"skipped_missing_information_sets": report[
					"skipped_missing_information_sets"
				],
				"skipped_zero_overlap_information_sets": report[
					"skipped_zero_overlap_information_sets"
				],
			},
			indent=2,
			sort_keys=True,
		)
	)


if __name__ == "__main__":
	main()
