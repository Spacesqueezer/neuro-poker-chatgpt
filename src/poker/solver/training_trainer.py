from dataclasses import dataclass

from poker.solver.training_checkpoint import (
	TrainingCheckpoint,
	create_checkpoint,
)


@dataclass(frozen=True)
class TrainingRunResult:
	steps: int
	status: str


class SolverTrainer:
	def __init__(self, objective):
		self.objective = objective
		self.current_step = 0

	def train(self, samples, steps=1):
		if steps < 0:
			raise ValueError("steps must be non-negative")

		for _ in range(steps):
			self.objective(samples)
			self.current_step += 1

		return TrainingRunResult(
			steps=self.current_step,
			status="completed",
		)

	def create_checkpoint(self):
		return create_checkpoint(
			step=self.current_step,
			metadata={
				"trainer": "SolverTrainer",
			},
		)

	def restore_checkpoint(self, checkpoint: TrainingCheckpoint):
		if not isinstance(checkpoint, TrainingCheckpoint):
			raise TypeError("invalid checkpoint")

		self.current_step = checkpoint.step
		return self.current_step
