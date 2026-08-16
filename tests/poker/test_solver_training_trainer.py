from poker.solver.training_trainer import SolverTrainer


def test_solver_trainer_contract():
	calls = []

	def objective(samples):
		calls.append(samples)

	trainer = SolverTrainer(objective)
	result = trainer.train((1, 2, 3), steps=2)

	assert result.steps == 2
	assert result.status == "completed"
	assert calls == [(1, 2, 3), (1, 2, 3)]
