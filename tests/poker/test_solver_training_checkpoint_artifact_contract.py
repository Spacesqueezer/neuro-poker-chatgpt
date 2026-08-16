from poker.solver.training_checkpoint import TrainingCheckpoint


def test_training_checkpoint_contains_metadata_contract():
	checkpoint = TrainingCheckpoint(
		step=1,
		metadata={"source": "test"},
	)

	assert checkpoint.step == 1
	assert checkpoint.metadata["source"] == "test"
