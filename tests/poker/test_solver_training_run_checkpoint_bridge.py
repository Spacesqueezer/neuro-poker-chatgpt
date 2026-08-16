from poker.solver import TrainingRunState


def test_training_run_state_can_be_embedded_in_checkpoint_payload():
	state = TrainingRunState(run_id="run-1", steps_completed=5)
	payload = state.to_dict()

	assert payload["run_id"] == "run-1"
	assert payload["steps_completed"] == 5
