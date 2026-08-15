import pytest

from poker.solver import (
	SolverTrainingMetrics,
	evaluate_solver_predictions,
)


def test_solver_training_validation_reports_loss_and_legal_top1_accuracy():
	metrics = evaluate_solver_predictions(
		predicted_probabilities=(
			(0.7, 0.1, 0.1, 0.05, 0.03, 0.02),
			(0.1, 0.1, 0.6, 0.1, 0.05, 0.05),
		),
		target_probabilities=(
			(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
			(0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
		),
		legal_masks=(
			(1.0, 0.0, 1.0, 0.0, 1.0, 1.0),
			(1.0, 0.0, 1.0, 0.0, 1.0, 1.0),
		),
	)

	assert isinstance(metrics, SolverTrainingMetrics)
	assert metrics.samples == 2
	assert metrics.mean_loss > 0.0
	assert metrics.accuracy == 1.0


def test_solver_training_validation_ignores_illegal_action_for_accuracy():
	metrics = evaluate_solver_predictions(
		predicted_probabilities=(
			(0.4, 0.9, 0.6, 0.0, 0.0, 0.0),
		),
		target_probabilities=(
			(0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
		),
		legal_masks=(
			(1.0, 0.0, 1.0, 0.0, 0.0, 0.0),
		),
	)

	assert metrics.accuracy == 1.0


def test_solver_training_validation_rejects_sample_count_mismatch():
	with pytest.raises(
		ValueError,
		match="solver validation sample counts must match",
	):
		evaluate_solver_predictions(
			predicted_probabilities=((1.0, 0.0, 0.0, 0.0, 0.0, 0.0),),
			target_probabilities=(),
			legal_masks=((1.0, 0.0, 0.0, 0.0, 0.0, 0.0),),
		)
