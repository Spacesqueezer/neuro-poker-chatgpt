from poker.solver import (
	TrainingCheckpointStore,
	create_checkpoint,
)


def test_checkpoint_store_round_trip(tmp_path):
	checkpoint = create_checkpoint(
		step=7,
		metadata={"trainer": "SolverTrainer"},
	)
	store = TrainingCheckpointStore(tmp_path / "nested" / "checkpoint.json")

	saved_path = store.save(checkpoint)
	restored = store.load()

	assert saved_path == store.path
	assert restored == checkpoint
