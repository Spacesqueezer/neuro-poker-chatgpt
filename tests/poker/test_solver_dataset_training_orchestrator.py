from poker.learning.solver_dataset_training_orchestrator import SolverDatasetTrainingOrchestrator


class FakeExecutor:
	def execute(self, records):
		return list(records)


def test_solver_dataset_training_orchestrator_delegates_execution():
	orchestrator = SolverDatasetTrainingOrchestrator(FakeExecutor())

	assert orchestrator.run([1, 2, 3]) == [1, 2, 3]
