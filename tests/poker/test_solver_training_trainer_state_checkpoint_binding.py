from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import (
	create_checkpoint,
	extract_checkpoint_trainer_state,
)


def test_checkpoint_binding_preserves_trainer_state():
	state = TrainerState(
		global_step=25,
		payload={"metric": 0.5},
	)

	checkpoint = create_checkpoint(
		step=25,
		trainer_state=state,
	)

	restored = extract_checkpoint_trainer_state(checkpoint)

	assert restored == state
