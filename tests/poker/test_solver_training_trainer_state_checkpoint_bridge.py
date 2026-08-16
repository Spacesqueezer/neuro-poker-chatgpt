from poker.solver.trainer_state import TrainerState
from poker.solver.trainer_state_checkpoint_bridge import (
	extract_trainer_state,
	attach_trainer_state,
)


def test_trainer_state_checkpoint_metadata_round_trip():
	state = TrainerState(global_step=42, payload={"loss": 1.5})

	metadata = attach_trainer_state({}, state)
	restored = extract_trainer_state(metadata)

	assert restored == state
