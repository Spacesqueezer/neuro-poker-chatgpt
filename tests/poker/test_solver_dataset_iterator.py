from poker.learning.solver_dataset_iterator import SolverDatasetIterator
from poker.learning.solver_dataset_loader import SolverDatasetRecord


def test_solver_dataset_iterator_preserves_stream_order():
	records = [
		SolverDatasetRecord([1.0], [1.0]),
		SolverDatasetRecord([2.0], [1.0]),
	]

	result = list(SolverDatasetIterator().iterate(iter(records)))

	assert result == records
