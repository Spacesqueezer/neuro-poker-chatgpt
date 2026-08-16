from poker.solver import (
	SolverTrainer,
	TrainingRunCheckpointPolicy,
	TrainingRunCoordinator,
	TrainingCheckpointStore,
)


class CountingStore:
	def __init__(self):
		self.count = 0

	def save(self, checkpoint):
		self.count += 1


def test_training_run_coordinator_checkpoints_on_interval(tmp_path):
	store = CountingStore()
	trainer = SolverTrainer(lambda samples: None, checkpoint_store=store)
	coordinator = TrainingRunCoordinator(
		trainer,
		TrainingRunCheckpointPolicy(interval_steps=2),
	)

	coordinator.train([], steps=2)

	assert store.count == 1


def test_checkpoint_policy_rejects_invalid_interval():
	policy = TrainingRunCheckpointPolicy(interval_steps=0)

	try:
		policy.should_checkpoint(1)
	except ValueError as error:
		assert str(error) == "interval_steps must be positive"
	else:
		raise AssertionError("expected ValueError")
