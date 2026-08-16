from abc import ABC, abstractmethod


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
