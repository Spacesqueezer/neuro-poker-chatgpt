from dataclasses import dataclass

from .training_evaluation_pipeline import build_training_evaluation_pipeline


@dataclass(frozen=True)
class SolverTrainingEvaluationRun:
	result: object
	status: str


def run_training_evaluation(predictions):
	result = build_training_evaluation_pipeline(predictions)

	return SolverTrainingEvaluationRun(
		result=result,
		status="completed",
	)
