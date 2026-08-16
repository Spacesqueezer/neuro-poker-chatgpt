from poker.solver import (
	TrainingRunState,
	attach_training_run_state,
	create_checkpoint,
	extract_training_run_state,
)


def test_training_run_state_can_be_embedded_in_checkpoint_payload():
	checkpoint = create_checkpoint(step=5, metadata={"trainer": "SolverTrainer"})
	state = TrainingRunState(
		run_id="run-1",
		steps_completed=5,
		created_at="2026-01-01T00:00:00+00:00",
	)

	bridged = attach_training_run_state(checkpoint, state)
	restored = extract_training_run_state(bridged)

	assert bridged.step == checkpoint.step
	assert bridged.metadata["trainer"] == "SolverTrainer"
	assert restored == state


def test_training_run_state_is_optional_in_checkpoint_payload():
	checkpoint = create_checkpoint(step=0)

	assert extract_training_run_state(checkpoint) is None
