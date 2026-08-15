from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SolverTrainingBatch:
	observations: tuple[tuple[float, ...], ...]
	probabilities: tuple[tuple[float, ...], ...]

	@property
	def size(self) -> int:
		return len(self.observations)


def build_solver_training_batch(samples: Sequence[object]) -> SolverTrainingBatch:
	return SolverTrainingBatch(
		observations=tuple(sample.observation for sample in samples),
		probabilities=tuple(sample.probabilities for sample in samples),
	)
