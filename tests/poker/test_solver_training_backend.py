from poker.solver import NullSolverTrainingBackend, SolverTrainingBackend


class DummyBatch:
	examples = (1, 2, 3)


def test_training_backend_contract():
	backend = NullSolverTrainingBackend()
	assert isinstance(backend, SolverTrainingBackend)
	assert backend.train_batch(DummyBatch())["samples"] == 3
	assert backend.predict((1.0,)) == ()
