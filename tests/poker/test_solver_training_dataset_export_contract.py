from poker.solver.training_batch import SolverTrainingBatch
from poker.solver.training_input import SolverTrainingInput


def test_training_contracts_remain_importable_for_consumer_layer():
	assert SolverTrainingBatch is not None
	assert SolverTrainingInput is not None
