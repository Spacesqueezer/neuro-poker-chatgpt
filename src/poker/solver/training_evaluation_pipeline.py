from dataclasses import dataclass

from .training_evaluation_metrics import build_evaluation_metrics


@dataclass(frozen=True)
class SolverTrainingEvaluationPipelineResult:
	metrics: object
	sample_count: int


def build_training_evaluation_pipeline(predictions):
	metrics = build_evaluation_metrics(predictions)

	return SolverTrainingEvaluationPipelineResult(
		metrics=metrics,
		sample_count=metrics.sample_count,
	)
