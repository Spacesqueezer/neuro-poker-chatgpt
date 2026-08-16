from dataclasses import dataclass


@dataclass(frozen=True)
class SolverTrainingValidationReport:
	batch_size: int
	observation_sizes: tuple[int, ...]
	valid: bool


def validate_solver_training_batch(batch):
	batch.validate()
	return SolverTrainingValidationReport(
		batch_size=batch.size,
		observation_sizes=tuple(sorted({len(item) for item in batch.observations})),
		valid=True,
	)
