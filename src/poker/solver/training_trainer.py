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
	def __init__(self, objective, backend=None, checkpoint_store=None):
		self.objective = objective
		self.backend = backend
		self.checkpoint_store = checkpoint_store
		self.current_step = 0

	def train(self, samples, steps=1):
		if steps < 0:
			raise ValueError("steps must be non-negative")

		for _ in range(steps):
			if self.backend is None:
				self.objective(samples)
			else:
				self.backend.train_batch(samples)
			self.current_step += 1

		return TrainingRunResult(
			steps=self.current_step,
			status="completed",
		)

	def create_checkpoint(self):
		return create_checkpoint(
			step=self.current_step,
			metadata=self.get_training_state(),
		)

	def restore_checkpoint(self, checkpoint: TrainingCheckpoint):
		if not isinstance(checkpoint, TrainingCheckpoint):
			raise TypeError("invalid checkpoint")

		if checkpoint.metadata:
			self.restore_training_state(checkpoint.metadata)
		else:
			self.current_step = checkpoint.step

		if self.current_step != checkpoint.step:
			raise ValueError("checkpoint state mismatch")

		return self.current_step

	def save_checkpoint(self):
		if self.checkpoint_store is None:
			raise ValueError("checkpoint store is not configured")

		checkpoint = self.create_checkpoint()
		self.checkpoint_store.save(checkpoint)
		return checkpoint

	def load_checkpoint(self):
		if self.checkpoint_store is None:
			raise ValueError("checkpoint store is not configured")

		checkpoint = self.checkpoint_store.load()
		self.restore_checkpoint(checkpoint)
		return checkpoint

	def export_checkpoint(self):
		return self.create_checkpoint()

	def import_checkpoint(self, checkpoint):
		return self.restore_checkpoint(checkpoint)

	def get_training_state(self):
		state = {
			"current_step": self.current_step,
			"trainer": "SolverTrainer",
		}

		if self.backend is not None:
			state["backend_state"] = self.backend.save_state()

		return state

	def restore_training_state(self, state):
		if not isinstance(state, dict):
			raise TypeError("invalid training state")

		step = state.get("current_step")
		if not isinstance(step, int) or step < 0:
			raise ValueError("invalid current_step")

		self.current_step = step

		if "backend_state" in state:
			if self.backend is None:
				raise ValueError("backend state requires backend")
			self.backend.load_state(state["backend_state"])

		return self.current_step

	def get_resume_summary(self):
		return {
			"current_step": self.current_step,
			"trainer": "SolverTrainer",
		}
