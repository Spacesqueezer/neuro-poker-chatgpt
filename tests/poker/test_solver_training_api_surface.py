from poker.solver.training_batch import SolverTrainingBatch
from poker.solver.training_input import SolverTrainingExample, SolverTrainingInput
from poker.solver.training_metrics import SolverTrainingMetrics
from poker.solver.training_objective import SolverTrainingObjective


def test_solver_training_contract_modules_are_available():
	assert SolverTrainingBatch is not None
	assert SolverTrainingExample is not None
	assert SolverTrainingInput is not None
	assert SolverTrainingMetrics is not None
	assert SolverTrainingObjective is not None
