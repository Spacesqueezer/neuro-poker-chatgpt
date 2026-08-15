from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SolverTrainingBatch:
	observations: tuple[tuple[float, ...], ...]
	probabilities: tuple[tuple[float, ...], ...]
	legal_masks: tuple[tuple[float, ...], ...]

	@property
	def size(self) -> int:
		return len(self.observations)

	def validate(self) -> None:
		if not self.observations:
			raise ValueError("training batch must not be empty")
		if len(self.observations) != len(self.probabilities):
			raise ValueError(
				"batch observations and probabilities must have equal length"
			)
		if len(self.observations) != len(self.legal_masks):
			raise ValueError(
				"batch observations and legal masks must have equal length"
			)

		observation_sizes = {
			len(observation)
			for observation in self.observations
		}
		if len(observation_sizes) != 1:
			raise ValueError(
				"batch observations must have consistent sizes"
			)

		for probabilities, legal_mask in zip(
			self.probabilities,
			self.legal_masks,
		):
			if len(probabilities) != 6:
				raise ValueError(
					"training probabilities must contain six actions"
				)
			if len(legal_mask) != 6:
				raise ValueError(
					"training legal masks must contain six actions"
				)
			if any(value not in {0.0, 1.0} for value in legal_mask):
				raise ValueError(
					"training legal masks must be binary"
				)
			if not any(value > 0.0 for value in legal_mask):
				raise ValueError(
					"training legal masks must contain legal actions"
				)
			if any(value < 0.0 for value in probabilities):
				raise ValueError(
					"training probabilities cannot contain negative values"
				)
			if abs(sum(probabilities) - 1.0) > 1e-9:
				raise ValueError(
					"training probabilities must sum to one"
				)
			if any(
				probability > 0.0 and legal_mask[index] == 0.0
				for index, probability in enumerate(probabilities)
			):
				raise ValueError(
					"training probability assigned to illegal action"
				)


def build_solver_training_batch(samples: Sequence[object]) -> SolverTrainingBatch:
	batch = SolverTrainingBatch(
		observations=tuple(sample.observation for sample in samples),
		probabilities=tuple(sample.probabilities for sample in samples),
		legal_masks=tuple(sample.legal_mask for sample in samples),
	)
	batch.validate()
	return batch
