from poker.solver.training_checkpoint import create_checkpoint, restore_checkpoint


def test_training_checkpoint_round_trip():
	checkpoint = create_checkpoint(5, {"epoch": 1})

	restored = restore_checkpoint(checkpoint)

	assert restored.step == 5
	assert restored.metadata == {"epoch": 1}
