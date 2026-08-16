from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import TrainingCheckpoint
from poker.solver.training_checkpoint_store import TrainingCheckpointStore


def test_checkpoint_store_round_trip_preserves_trainer_state(tmp_path):
	state = TrainerState(
		global_step=12,
		payload={"backend_state": {"model": {"weight": 3}}},
	)

	checkpoint = TrainingCheckpoint(
		step=12,
		metadata={"trainer_state": state.serialize()},
	)

	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")
	store.save(checkpoint)

	restored = store.load()
	restored_state = TrainerState.deserialize(
		restored.metadata["trainer_state"],
	)

	assert restored_state.global_step == 12
	assert restored_state.payload["backend_state"]["model"]["weight"] == 3
