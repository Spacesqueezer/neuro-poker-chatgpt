from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingRunResult:
	steps: int
	status: str


class SolverTrainer:
	def __init__(self, objective):
		self.objective = objective

	def train(self, samples, steps=1):
		if steps < 0:
			raise ValueError("steps must be non-negative")

		for _ in range(steps):
			self.objective(samples)

		return TrainingRunResult(
			steps=steps,
			status="completed",
		)
