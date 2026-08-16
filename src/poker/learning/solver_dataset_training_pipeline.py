from collections.abc import Iterable, Iterator

from poker.learning.solver_dataset_batch import SolverDatasetBatch


class SolverDatasetTrainingPipeline:
	def __init__(self, batch_iterator, trainer):
		self.batch_iterator = batch_iterator
		self.trainer = trainer

	def run(self, records: Iterable) -> Iterator:
		for batch in self.batch_iterator.iterate(records):
			yield self.trainer.train_batch(batch)
