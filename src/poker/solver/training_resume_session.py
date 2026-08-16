class TrainingResumeSession:
	def __init__(self, coordinator, checkpoint_store):
		self.coordinator = coordinator
		self.checkpoint_store = checkpoint_store

	def restore(self):
		checkpoint = self.checkpoint_store.restore_artifact(self.coordinator)
		return checkpoint

	def resume(self):
		self.restore()
		return self.coordinator

	def resume_training(self, samples, steps):
		checkpoint = self.restore()
		return self.coordinator.train(samples, steps)
