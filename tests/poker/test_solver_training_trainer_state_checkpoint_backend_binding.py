from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import TrainingCheckpoint


def test_checkpoint_can_carry_serialized_trainer_state():
	state = TrainerState(
		global_step=12,
		payload={"backend_state": {"model": {"weight": 3}}},
	)

	checkpoint = TrainingCheckpoint(
		step=12,
		metadata={"trainer_state": state.serialize()},
	)

	restored = TrainerState.deserialize(
		checkpoint.metadata["trainer_state"],
	)

	assert restored.global_step == 12
	assert restored.payload["backend_state"] == {"model": {"weight": 3}}
