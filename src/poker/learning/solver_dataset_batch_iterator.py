from collections.abc import Iterable, Iterator

from poker.learning.solver_dataset_batch import SolverDatasetBatch, SolverDatasetBatcher
from poker.learning.solver_dataset_loader import SolverDatasetRecord


class SolverDatasetBatchIterator:
	def __init__(self, batch_size: int):
		self.batcher = SolverDatasetBatcher()
		self.batch_size = batch_size

	def iterate(self, records: Iterable[SolverDatasetRecord]) -> Iterator[SolverDatasetBatch]:
		buffer = []
		for record in records:
			buffer.append(record)
			if len(buffer) == self.batch_size:
				yield from self.batcher.create_batches(buffer, self.batch_size)
				buffer = []

		if buffer:
			yield from self.batcher.create_batches(buffer, self.batch_size)
