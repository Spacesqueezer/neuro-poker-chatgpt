from poker.learning.solver_dataset_training_pipeline import SolverDatasetTrainingPipeline


class FakeIterator:
	def iterate(self, records):
		yield from records


class FakeTrainer:
	def train_batch(self, batch):
		return batch


def test_solver_dataset_training_pipeline_forwards_batches():
	pipeline = SolverDatasetTrainingPipeline(FakeIterator(), FakeTrainer())

	result = list(pipeline.run([1, 2, 3]))

	assert result == [1, 2, 3]
