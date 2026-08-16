from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class TrainingRunState:
	run_id: str
	steps_completed: int = 0
	created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class TrainingRunCheckpointPolicy:
	interval_steps: int

	def should_checkpoint(self, step):
		if self.interval_steps <= 0:
			raise ValueError("interval_steps must be positive")

		return step > 0 and step % self.interval_steps == 0


class TrainingRunCoordinator:
	def __init__(self, trainer, checkpoint_policy=None, state=None):
		self.trainer = trainer
		self.checkpoint_policy = checkpoint_policy
		self.state = state

	def train(self, samples, steps):
		result = self.trainer.train(samples, steps=steps)

		if self.state is not None:
			self.state = TrainingRunState(
				run_id=self.state.run_id,
				steps_completed=result.steps,
				created_at=self.state.created_at,
			)

		if self.checkpoint_policy is not None:
			if self.checkpoint_policy.should_checkpoint(result.steps):
				self.trainer.save_checkpoint()

		return result
