from poker.solver.training_evaluation_pipeline import (
	SolverTrainingEvaluationPipelineResult,
	build_training_evaluation_pipeline,
)


def test_training_evaluation_pipeline_contract():
	result = build_training_evaluation_pipeline((True, False, True))

	assert isinstance(result, SolverTrainingEvaluationPipelineResult)
	assert result.sample_count == 3
	assert result.metrics.accuracy == 2 / 3
