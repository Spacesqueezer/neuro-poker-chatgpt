from poker.learning.solver_dataset_batch import SolverDatasetBatcher
from poker.learning.solver_dataset_loader import SolverDatasetRecord


def test_solver_dataset_batcher_groups_records():
	records = [
		SolverDatasetRecord([1.0], [1.0]),
		SolverDatasetRecord([2.0], [1.0]),
		SolverDatasetRecord([3.0], [1.0]),
	]

	batches = SolverDatasetBatcher().create_batches(records, 2)

	assert len(batches) == 2
	assert batches[0].observations == [[1.0], [2.0]]
	assert batches[1].observations == [[3.0]]
