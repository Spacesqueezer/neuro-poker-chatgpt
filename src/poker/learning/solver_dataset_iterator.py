from collections.abc import Iterable, Iterator

from poker.learning.solver_dataset_loader import SolverDatasetRecord


class SolverDatasetIterator:
	def iterate(self, records: Iterable[SolverDatasetRecord]) -> Iterator[SolverDatasetRecord]:
		for record in records:
			yield record
