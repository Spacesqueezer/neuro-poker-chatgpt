from poker.solver.training_input import SolverTrainingObjectiveContract


def test_solver_training_objective_contract_validates_soft_targets():
	SolverTrainingObjectiveContract.validate_target(
		(1.0, 0.0, 1.0, 0.0, 1.0, 1.0),
		(0.1, 0.0, 0.2, 0.0, 0.6, 0.1),
	)
