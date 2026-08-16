from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import create_checkpoint, extract_checkpoint_trainer_state


def test_runtime_restore_keeps_training_progress():
	state = TrainerState(
		global_step=250,
		payload={
			"epoch": 3,
			"metrics": {"loss": 0.05},
		},
	)

	checkpoint = create_checkpoint(
		step=250,
		trainer_state=state,
	)

	restored = extract_checkpoint_trainer_state(checkpoint)

	assert restored.global_step == 250
	assert restored.payload["epoch"] == 3
	assert restored.payload["metrics"]["loss"] == 0.05
