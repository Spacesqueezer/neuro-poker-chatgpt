class SolverDatasetTrainingExecutor:
	def __init__(self, pipeline):
		self.pipeline = pipeline

	def execute(self, records):
		results = []
		for result in self.pipeline.run(records):
			results.append(result)
		return results
