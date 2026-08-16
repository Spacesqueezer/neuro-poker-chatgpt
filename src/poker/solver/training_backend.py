from abc import ABC, abstractmethod
from dataclasses import dataclass


class SolverTrainingBackend(ABC):
	"""Framework-neutral boundary for consuming solver training batches."""

	@abstractmethod
	def train_batch(self, batch):
		"""Consume one validated solver training batch."""
		raise NotImplementedError

	@abstractmethod
	def predict(self, observation):
		"""Return backend policy output for one observation."""
		raise NotImplementedError

	@abstractmethod
	def save_state(self):
		"""Return serializable backend-owned state."""
		raise NotImplementedError

	@abstractmethod
	def load_state(self, state):
		"""Restore previously exported backend-owned state."""
		raise NotImplementedError


@dataclass(frozen=True)
class SolverTrainingBackendState:
	payload: dict


class NullSolverTrainingBackend(SolverTrainingBackend):
	"""Minimal backend used to validate the contract without ML dependencies."""

	def train_batch(self, batch):
		if batch is None:
			raise ValueError("batch is required")
		return {"status": "accepted", "samples": len(batch.examples)}

	def predict(self, observation):
		if observation is None:
			raise ValueError("observation is required")
		return tuple()

	def save_state(self):
		return SolverTrainingBackendState(payload={})

	def load_state(self, state):
		if not isinstance(state, SolverTrainingBackendState):
			raise TypeError("invalid backend state")
