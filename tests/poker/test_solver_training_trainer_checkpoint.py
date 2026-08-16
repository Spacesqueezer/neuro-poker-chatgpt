from poker.solver.training_trainer import SolverTrainer


def test_solver_trainer_checkpoint_round_trip():
	trainer = SolverTrainer(lambda samples: None)

	trainer.train([], steps=3)
	checkpoint = trainer.create_checkpoint()

	restored = SolverTrainer(lambda samples: None)
	restored.restore_checkpoint(checkpoint)

	assert checkpoint.step == 3
	assert checkpoint.metadata == {
		"current_step": 3,
		"trainer": "SolverTrainer",
	}
	assert restored.current_step == 3


def test_solver_trainer_state_round_trip():
	trainer = SolverTrainer(lambda samples: None)

	trainer.train([], steps=4)
	state = trainer.get_training_state()

	restored = SolverTrainer(lambda samples: None)
	restored.restore_training_state(state)

	assert state == {
		"current_step": 4,
		"trainer": "SolverTrainer",
	}
	assert restored.current_step == 4


def test_solver_trainer_resume_summary_matches_state():
	trainer = SolverTrainer(lambda samples: None)
	trainer.train([], steps=5)

	assert trainer.get_resume_summary() == {
		"current_step": 5,
		"trainer": "SolverTrainer",
	}


def test_solver_trainer_restore_training_state_rejects_invalid_step():
	trainer = SolverTrainer(lambda samples: None)

	try:
		trainer.restore_training_state({"current_step": -1})
	except ValueError as error:
		assert str(error) == "invalid current_step"
	else:
		raise AssertionError("invalid training state was accepted")
