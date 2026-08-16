from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import (
	create_checkpoint,
	extract_checkpoint_trainer_state,
)


def test_checkpoint_round_trip_restores_trainer_state():
	state = TrainerState(
		global_step=100,
		payload={"loss": 0.1},
	)

	checkpoint = create_checkpoint(
		step=100,
		trainer_state=state,
	)

	restored = extract_checkpoint_trainer_state(checkpoint)

	assert restored == state
