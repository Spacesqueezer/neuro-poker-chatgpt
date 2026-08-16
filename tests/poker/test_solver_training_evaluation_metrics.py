from poker.solver.training_evaluation_metrics import (
	SolverTrainingEvaluationMetrics,
	build_evaluation_metrics,
)


def test_training_evaluation_metrics_contract():
	metrics = build_evaluation_metrics((True, False, True))

	assert isinstance(metrics, SolverTrainingEvaluationMetrics)
	assert metrics.sample_count == 3
	assert metrics.correct_count == 2
	assert metrics.accuracy == 2 / 3


def test_training_evaluation_metrics_empty_input():
	metrics = build_evaluation_metrics(())

	assert metrics.sample_count == 0
	assert metrics.correct_count == 0
	assert metrics.accuracy == 0.0
