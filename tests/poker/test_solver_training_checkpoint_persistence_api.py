from poker.solver import TrainingRunState


def test_training_run_state_is_available_for_checkpoint_api():
	state = TrainingRunState(run_id="checkpoint-api")

	assert state.run_id == "checkpoint-api"
