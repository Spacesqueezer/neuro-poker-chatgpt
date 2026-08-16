from poker.solver.training_evaluation import (
	SolverTrainingEvaluationReport,
	evaluate_solver_predictions,
)


class Report:
	valid = True


def test_solver_training_evaluation_accepts_valid_report():
	result = evaluate_solver_predictions(
		Report(),
		((0.1, 0.9),),
	)

	assert isinstance(result, SolverTrainingEvaluationReport)
	assert result.validated is True
	assert result.sample_count == 1


def test_solver_training_evaluation_rejects_invalid_report():
	class InvalidReport:
		valid = False

	try:
		evaluate_solver_predictions(InvalidReport(), ())
		raise AssertionError("evaluation should fail")
	except ValueError:
		pass
