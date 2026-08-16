import pytest

from poker.solver import (
	NullSolverTrainingBackend,
	SolverTrainingBackendState,
)


def test_null_backend_state_round_trip_contract():
	backend = NullSolverTrainingBackend()

	state = backend.save_state()
	backend.load_state(state)

	assert state == SolverTrainingBackendState(payload={})


def test_null_backend_rejects_invalid_state():
	backend = NullSolverTrainingBackend()

	with pytest.raises(TypeError, match="invalid backend state"):
		backend.load_state({})
