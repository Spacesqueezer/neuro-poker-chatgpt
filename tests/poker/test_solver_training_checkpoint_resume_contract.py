from poker.solver.training_checkpoint import create_checkpoint
from poker.solver.training_checkpoint_store import TrainingCheckpointStore


def test_checkpoint_store_preserves_metadata(tmp_path):
	checkpoint = create_checkpoint(
		step=10,
		metadata={
			"training_run_state": {
				"run_id": "run-1",
				"steps_completed": 10,
			}
		},
	)

	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")
	store.save(checkpoint)

	restored = store.load()

	assert restored.step == 10
	assert restored.metadata["training_run_state"]["run_id"] == "run-1"
