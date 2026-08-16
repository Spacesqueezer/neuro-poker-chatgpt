from poker.solver import TrainingRunState


def test_training_checkpoint_integration_placeholder():
	state = TrainingRunState(run_id="run-1")

	assert state.run_id == "run-1"
