class SolverDatasetTrainingOrchestrator:
	def __init__(self, executor):
		self.executor = executor

	def run(self, records):
		return self.executor.execute(records)
