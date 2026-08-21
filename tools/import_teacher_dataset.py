import argparse
import json
from pathlib import Path

from poker.learning import TeacherRecordImporter
from poker.learning.dataset import LearningDatasetWriter


def main():
	parser = argparse.ArgumentParser(
		description="Converts solver-local teacher records into LearningSample dataset."
	)
	parser.add_argument("--input", required=True, help="Path to teacher records JSON file")
	parser.add_argument("--output", required=True, help="Path to output JSONL dataset")
	args = parser.parse_args()

	input_path = Path(args.input)
	output_path = Path(args.output)

	if not input_path.exists():
		raise FileNotFoundError(f"Input file {args.input} not found.")

	payload = json.loads(input_path.read_text(encoding="utf-8"))

	if "average_strategy" in payload and "records" not in payload:
		raise ValueError(
			f"Input file {args.input} appears to be a raw MCCFR strategy artifact, not a teacher records file.\n"
			"Please run `python tools/export_teacher_records.py` first to convert the strategy into teacher records."
		)

	small_blind = payload.get("benchmark", {}).get("small_blind", 1)
	big_blind = payload.get("benchmark", {}).get("big_blind", 2)
	action_abstraction = payload.get("action_abstraction")

	importer = TeacherRecordImporter(
		small_blind=small_blind,
		big_blind=big_blind,
		action_abstraction=action_abstraction,
	)

	# Clear output file if it exists
	if output_path.exists():
		output_path.unlink()

	writer = LearningDatasetWriter(output_path)
	records = payload.get("records", [])
	imported_count = 0

	for record in records:
		sample = importer.import_record(record)
		writer.write(sample)
		imported_count += 1

	print(json.dumps({
		"input": args.input,
		"output": args.output,
		"imported_samples": imported_count,
	}, indent=2))


if __name__ == "__main__":
	main()
