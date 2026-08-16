from poker.solver import (
	TrainingCheckpoint,
	TrainingCheckpointStore,
	TrainingRunCoordinator,
	TrainingRunState,
	attach_training_run_state,
)


class FakeTrainer:
	def restore_checkpoint(self, checkpoint):
		self.restored = checkpoint
		return checkpoint


def test_checkpoint_store_restores_into_coordinator(tmp_path):
	persisted_state = TrainingRunState(
		run_id="persisted-run",
		steps_completed=12,
		created_at="2026-08-16T00:00:00+00:00",
	)
	checkpoint = attach_training_run_state(
		TrainingCheckpoint(step=12, metadata={}),
		persisted_state,
	)
	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")
	store.save(checkpoint)

	trainer = FakeTrainer()
	coordinator = TrainingRunCoordinator(
		trainer,
		state=TrainingRunState(run_id="fresh-run"),
	)

	loaded = store.restore_into_coordinator(coordinator)

	assert loaded == checkpoint
	assert trainer.restored == checkpoint
	assert coordinator.state == persisted_state
