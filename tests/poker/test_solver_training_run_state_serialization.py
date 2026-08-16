from poker.solver import TrainingRunState


def test_training_run_state_round_trip():
	state = TrainingRunState(
		run_id="run-1",
		steps_completed=12,
		created_at="2026-01-01T00:00:00+00:00",
	)

	restored = TrainingRunState.from_dict(state.to_dict())

	assert restored == state
