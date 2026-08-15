from dataclasses import dataclass

from poker.solver.training_batch import build_solver_training_batch


@dataclass(frozen=True)
class Sample:
	observation: tuple[float, ...]
	probabilities: tuple[float, ...]


def test_solver_training_batch_contract_preserves_arrays():
	batch = build_solver_training_batch(
		[
			Sample((1.0, 2.0), (0.5, 0.5)),
		]
	)

	assert batch.size == 1
	assert batch.observations == ((1.0, 2.0),)
	assert batch.probabilities == ((0.5, 0.5),)
