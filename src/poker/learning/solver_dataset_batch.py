from dataclasses import dataclass

from poker.learning.solver_dataset_loader import SolverDatasetRecord


@dataclass(frozen=True)
class SolverDatasetBatch:
	observations: list[list[float]]
	action_probabilities: list[list[float]]


class SolverDatasetBatcher:
	def create_batches(self, records: list[SolverDatasetRecord], batch_size: int):
		if batch_size <= 0:
			raise ValueError("batch_size must be positive")

		batches = []
		for index in range(0, len(records), batch_size):
			chunk = records[index:index + batch_size]
			batches.append(
				SolverDatasetBatch(
					observations=[record.observation for record in chunk],
					action_probabilities=[record.action_probabilities for record in chunk],
				)
			)
		return batches
