import argparse
import json
from pathlib import Path

from poker.solver import (
	OPPONENT_PROFILE_FEATURE_NAMES,
	SOLVER_SUPERVISED_SAMPLE_VERSION,
	SolverSupervisedDatasetAnalyzer,
	SolverSupervisedDatasetWriter,
	build_learning_bridge_records,
	build_solver_supervised_samples,
	load_teacher_record_export,
)


SOLVER_SUPERVISED_EXPORT_MANIFEST_VERSION = 1


def load_encoded_profiles(path):
	payload = json.loads(Path(path).read_text(encoding="utf-8"))
	if not isinstance(payload, dict):
		raise ValueError("encoded profiles file must be a JSON object")
	if set(payload) != {"player_0", "player_1"}:
		raise ValueError(
			"encoded profiles must contain player_0 and player_1"
		)

	profiles = {}
	for player_name, values in payload.items():
		if (
			not isinstance(values, list)
			or len(values) != len(OPPONENT_PROFILE_FEATURE_NAMES)
			or any(
				not isinstance(value, (int, float))
				or isinstance(value, bool)
				for value in values
			)
		):
			raise ValueError(
				f"encoded profile for {player_name} is invalid"
			)
		profiles[player_name] = tuple(float(value) for value in values)
	return profiles


def export_solver_supervised_dataset(
	teacher_path,
	profiles_path,
	output,
	manifest_output=None,
):
	teacher = load_teacher_record_export(teacher_path)
	profiles = load_encoded_profiles(profiles_path)
	records = build_learning_bridge_records(
		teacher,
		opponent_profiles=profiles,
	)
	samples = build_solver_supervised_samples(records)

	output = Path(output)
	output.parent.mkdir(parents=True, exist_ok=True)
	if output.exists():
		output.unlink()

	writer = SolverSupervisedDatasetWriter(output)
	written = writer.write_many(samples)
	analysis = SolverSupervisedDatasetAnalyzer().analyze(output)

	manifest_path = (
		Path(manifest_output)
		if manifest_output is not None
		else output.with_suffix(output.suffix + ".manifest.json")
	)
	manifest_path.parent.mkdir(parents=True, exist_ok=True)

	manifest = {
		"format_version": SOLVER_SUPERVISED_EXPORT_MANIFEST_VERSION,
		"dataset": str(output),
		"sample_version": SOLVER_SUPERVISED_SAMPLE_VERSION,
		"sample_count": written,
		"profile_feature_names": list(OPPONENT_PROFILE_FEATURE_NAMES),
		"source_teacher": {
			"format_version": teacher["format_version"],
			"source_strategy": teacher["source_strategy"],
			"record_count": teacher["record_count"],
			"skipped_missing_information_sets": teacher[
				"skipped_missing_information_sets"
			],
			"skipped_zero_overlap_information_sets": teacher[
				"skipped_zero_overlap_information_sets"
			],
		},
		"analysis": analysis,
	}
	manifest_path.write_text(
		json.dumps(
			manifest,
			indent=2,
			sort_keys=True,
		) + "\n",
		encoding="utf-8",
	)
	return manifest


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--teacher", required=True)
	parser.add_argument("--profiles", required=True)
	parser.add_argument("--output", required=True)
	parser.add_argument("--manifest-output")
	args = parser.parse_args()

	manifest = export_solver_supervised_dataset(
		teacher_path=args.teacher,
		profiles_path=args.profiles,
		output=args.output,
		manifest_output=args.manifest_output,
	)
	print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
	main()
