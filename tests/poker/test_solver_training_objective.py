import pytest

from poker.solver.training_objective import SolverTrainingObjective


def test_solver_training_objective_ignores_masked_actions():
	loss = SolverTrainingObjective.cross_entropy(
		(0.5, 0.5, 0.0),
		(1.0, 0.0, 0.0),
		(1.0, 0.0, 0.0),
	)

	assert loss == pytest.approx(0.6931471805599453)


def test_solver_training_objective_rejects_invalid_shapes():
	with pytest.raises(ValueError, match="prediction and target sizes must match"):
		SolverTrainingObjective.cross_entropy(
			(0.5, 0.5),
			(1.0,),
			(1.0, 0.0),
		)
