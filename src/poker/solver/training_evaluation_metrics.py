from dataclasses import dataclass


@dataclass(frozen=True)
class SolverTrainingEvaluationMetrics:
	sample_count: int
	correct_count: int
	accuracy: float


def build_evaluation_metrics(predictions):
	sample_count = len(predictions)
	correct_count = sum(1 for item in predictions if item)

	accuracy = (
		correct_count / sample_count
		if sample_count
		else 0.0
	)

	return SolverTrainingEvaluationMetrics(
		sample_count=sample_count,
		correct_count=correct_count,
		accuracy=accuracy,
	)
