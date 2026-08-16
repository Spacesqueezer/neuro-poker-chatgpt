from poker.solver.trainer_state import TrainerState


def test_trainer_state_round_trip():
	state = TrainerState(
		global_step=42,
		payload={"model": "future"},
	)

	restored = TrainerState.deserialize(state.serialize())

	assert restored == state
