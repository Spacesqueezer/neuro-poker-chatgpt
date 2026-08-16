from poker.solver import TrainingCheckpointStore


def test_checkpoint_store_exposes_artifact_resume_boundary(tmp_path):
	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")

	assert hasattr(store, "restore_artifact")
