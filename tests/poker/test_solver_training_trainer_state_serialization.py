from poker.solver.trainer_state import TrainerState


def test_trainer_state_serialize_deserialize_round_trip():
	state = TrainerState(
		global_step=42,
		payload={"backend_state": {"model": {"weight": 1}}},
	)

	serialized = state.serialize()
	restored = TrainerState.deserialize(serialized)

	assert restored == state
