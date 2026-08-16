from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import (
	create_checkpoint,
	extract_checkpoint_trainer_state,
)


def test_checkpoint_restores_trainer_state():
	state = TrainerState(global_step=12, payload={"metric": 1})

	checkpoint = create_checkpoint(12, trainer_state=state)
	restored = extract_checkpoint_trainer_state(checkpoint)

	assert restored == state
