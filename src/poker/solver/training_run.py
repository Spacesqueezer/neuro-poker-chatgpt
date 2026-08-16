from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingRunCheckpointPolicy:
	interval_steps: int

	def should_checkpoint(self, step):
		if self.interval_steps <= 0:
			raise ValueError("interval_steps must be positive")

		return step > 0 and step % self.interval_steps == 0


class TrainingRunCoordinator:
	def __init__(self, trainer, checkpoint_policy=None):
		self.trainer = trainer
		self.checkpoint_policy = checkpoint_policy

	def train(self, samples, steps):
		result = self.trainer.train(samples, steps=steps)

		if self.checkpoint_policy is not None:
			if self.checkpoint_policy.should_checkpoint(result.steps):
				self.trainer.save_checkpoint()

		return result
