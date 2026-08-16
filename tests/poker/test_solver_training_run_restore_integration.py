from poker.solver import (
	TrainingCheckpoint,
	TrainingRunCoordinator,
	TrainingRunState,
	attach_training_run_state,
)


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


def test_training_run_restore_uses_checkpoint_run_state_metadata():
	trainer = FakeTrainer()
	coordinator = TrainingRunCoordinator(
		trainer,
		state=TrainingRunState(run_id="fresh-run"),
	)
	persisted_state = TrainingRunState(
		run_id="persisted-run",
		steps_completed=12,
		created_at="2026-08-16T00:00:00+00:00",
	)
	checkpoint = attach_training_run_state(
		TrainingCheckpoint(step=12, metadata={}),
		persisted_state,
	)

	coordinator.restore_checkpoint(checkpoint)

	assert coordinator.state == persisted_state
