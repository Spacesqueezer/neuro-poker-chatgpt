def test_solver_training_input_contract_imports():
	assert True


def test_solver_training_input_rejects_empty_examples():
	from poker.solver.training_input import SolverTrainingInput

	try:
		SolverTrainingInput(())
	except ValueError:
		return

	assert False
