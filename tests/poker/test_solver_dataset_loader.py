import json

from poker.learning.solver_dataset_loader import SolverDatasetLoader


def test_solver_dataset_loader_reads_jsonl(tmp_path):
	path = tmp_path / "dataset.jsonl"
	path.write_text(
		json.dumps({"observation": [1.0], "action_probabilities": [0.5, 0.5]}) + "\n",
		encoding="utf-8",
	)

	records = SolverDatasetLoader().load(path)

	assert len(records) == 1
	assert records[0].observation == [1.0]
	assert records[0].action_probabilities == [0.5, 0.5]
