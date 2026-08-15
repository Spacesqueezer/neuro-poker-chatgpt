from poker.solver.training_metrics import SolverTrainingMetrics


def test_solver_training_metrics_contract_serializes():
	metrics = SolverTrainingMetrics(samples=10, mean_loss=0.5, accuracy=0.8)

	assert metrics.as_dict() == {
		"samples": 10,
		"mean_loss": 0.5,
		"accuracy": 0.8,
	}
