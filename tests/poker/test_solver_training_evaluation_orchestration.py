from poker.solver.training_evaluation_orchestration import (
	SolverTrainingEvaluationRun,
	run_training_evaluation,
)


def test_training_evaluation_orchestration_contract():
	run = run_training_evaluation((True, True, False, True))

	assert isinstance(run, SolverTrainingEvaluationRun)
	assert run.status == "completed"
	assert run.result.sample_count == 4
