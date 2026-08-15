from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SolverTrainingBatch:
	observations: tuple[tuple[float, ...], ...]
	probabilities: tuple[tuple[float, ...], ...]

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

		observation_sizes = {
			len(observation)
			for observation in self.observations
		}
		if len(observation_sizes) != 1:
			raise ValueError(
				"batch observations must have consistent sizes"
			)

		for probabilities in self.probabilities:
			if len(probabilities) != 6:
				raise ValueError(
					"training probabilities must contain six actions"
				)
			if any(value < 0.0 for value in probabilities):
				raise ValueError(
					"training probabilities cannot contain negative values"
				)
			if abs(sum(probabilities) - 1.0) > 1e-9:
				raise ValueError(
					"training probabilities must sum to one"
				)


def build_solver_training_batch(samples: Sequence[object]) -> SolverTrainingBatch:
	batch = SolverTrainingBatch(
		observations=tuple(sample.observation for sample in samples),
		probabilities=tuple(sample.probabilities for sample in samples),
	)
	batch.validate()
	return batch
