from poker.solver.trainer_state import TrainerState


def test_trainer_state_preserves_backend_state_payload():
	state = TrainerState(
		global_step=42,
		payload={"backend_state": {"model": {"weight": 1}}},
	)

	restored = TrainerState.deserialize(state.serialize())

	assert restored.payload["backend_state"] == {"model": {"weight": 1}}
