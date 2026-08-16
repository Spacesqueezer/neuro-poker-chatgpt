from poker.solver.trainer_backend_state import TrainerBackendState
from poker.solver.training_checkpoint import TrainingCheckpoint
from poker.solver.training_checkpoint_store import TrainingCheckpointStore


def test_checkpoint_store_preserves_backend_state_metadata(tmp_path):
	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")

	state = TrainerBackendState(
		global_step=50,
		model_state={"weight": 1},
	)

	checkpoint = TrainingCheckpoint(
		step=50,
		metadata={"backend_state": state.to_payload()},
	)

	store.save(checkpoint)

	restored = store.load()

	restored_state = TrainerBackendState.from_payload(
		restored.metadata["backend_state"]
	)

	assert restored_state.global_step == 50
	assert restored_state.model_state["weight"] == 1
