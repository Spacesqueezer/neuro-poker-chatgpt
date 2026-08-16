from poker.learning.solver_dataset_batch_iterator import SolverDatasetBatchIterator
from poker.learning.solver_dataset_loader import SolverDatasetRecord


def test_solver_dataset_batch_iterator_creates_batches_from_stream():
	records = [
		SolverDatasetRecord([1.0], [1.0]),
		SolverDatasetRecord([2.0], [1.0]),
		SolverDatasetRecord([3.0], [1.0]),
	]

	batches = list(SolverDatasetBatchIterator(2).iterate(iter(records)))

	assert len(batches) == 2
	assert batches[0].observations == [[1.0], [2.0]]
	assert batches[1].observations == [[3.0]]
