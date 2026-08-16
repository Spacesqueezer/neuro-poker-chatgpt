from poker.solver import TrainingRunCoordinator


class FakeTrainer:
	def restore_checkpoint(self, checkpoint):
		self.restored = checkpoint
		return checkpoint


def test_training_run_restore_delegates_checkpoint():
	trainer = FakeTrainer()
	coordinator = TrainingRunCoordinator(trainer)
	checkpoint = type("Checkpoint", (), {"step": 5})()

	result = coordinator.restore_checkpoint(checkpoint)

	assert trainer.restored == checkpoint
	assert result == checkpoint
