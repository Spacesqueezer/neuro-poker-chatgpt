class TrainingResumeSession:
	def __init__(self, coordinator, checkpoint_store):
		self.coordinator = coordinator
		self.checkpoint_store = checkpoint_store

	def restore(self):
		return self.checkpoint_store.restore_artifact(self.coordinator)

	def resume(self):
		self.restore()
		return self.coordinator
