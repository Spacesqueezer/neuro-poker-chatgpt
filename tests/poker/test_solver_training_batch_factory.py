from dataclasses import dataclass

from poker.solver.training_batch import build_solver_training_batch


@dataclass(frozen=True)
class Sample:
	observation: tuple[float, ...]
	probabilities: tuple[float, ...]


def test_build_solver_training_batch_creates_valid_batch():
	batch = build_solver_training_batch(
		(
			Sample(
				observation=(0.0, 1.0),
				probabilities=(0.2, 0.2, 0.2, 0.2, 0.1, 0.1),
			),
		)
	)

	assert batch.size == 1
	assert batch.observations == ((0.0, 1.0),)
