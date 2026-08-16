from dataclasses import dataclass


@dataclass(frozen=True)
class SolverTrainingEvaluationReport:
	validated: bool
	sample_count: int
	accuracy: float | None = None


def evaluate_solver_predictions(validation_report, predictions):
	if not validation_report.valid:
		raise ValueError("Validation report is not valid")

	return SolverTrainingEvaluationReport(
		validated=True,
		sample_count=len(predictions),
		accuracy=None,
	)
