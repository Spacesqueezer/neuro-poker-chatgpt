from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import TrainingCheckpoint


def test_checkpoint_restore_contract_exposes_trainer_state():
	state = TrainerState(
		global_step=25,
		payload={"backend_state": {"model": {"weight": 7}}},
	)

	checkpoint = TrainingCheckpoint(
		step=25,
		metadata={"trainer_state": state.serialize()},
	)

	restored = TrainerState.deserialize(
		checkpoint.metadata["trainer_state"],
	)

	assert restored.global_step == 25
	assert restored.payload["backend_state"]["model"]["weight"] == 7
