from poker.learning.solver_dataset_training_executor import SolverDatasetTrainingExecutor


class FakePipeline:
	def run(self, records):
		yield from records


def test_solver_dataset_training_executor_collects_results():
	executor = SolverDatasetTrainingExecutor(FakePipeline())

	assert executor.execute([1, 2]) == [1, 2]
