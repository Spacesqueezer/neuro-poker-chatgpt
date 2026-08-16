from .training_checkpoint import extract_checkpoint_trainer_state


class TrainingResumeSession:
	def __init__(self, coordinator, checkpoint_store):
		self.coordinator = coordinator
		self.checkpoint_store = checkpoint_store
		self.trainer_state = None

	def restore(self):
		checkpoint = self.checkpoint_store.restore_artifact(self.coordinator)
		self.trainer_state = extract_checkpoint_trainer_state(checkpoint)
		return checkpoint

	def resume(self):
		self.restore()
		return self.coordinator

	def resume_training(self, samples, steps):
		checkpoint = self.restore()
		return self.coordinator.train(samples, steps)
