from poker.solver.trainer_backend_state import TrainerBackendState
from poker.solver.training_checkpoint import TrainingCheckpoint


def test_checkpoint_can_carry_backend_state_payload():
	state = TrainerBackendState(
		global_step=25,
		model_state={"layer": "weights"},
	)

	checkpoint = TrainingCheckpoint(
		step=25,
		metadata={"backend_state": state.to_payload()},
	)

	restored = TrainerBackendState.from_payload(
		checkpoint.metadata["backend_state"]
	)

	assert restored.global_step == 25
	assert restored.model_state["layer"] == "weights"
