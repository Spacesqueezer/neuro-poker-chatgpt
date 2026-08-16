from poker.solver.training_trainer import SolverTrainer


def test_solver_trainer_checkpoint_round_trip():
	trainer = SolverTrainer(lambda samples: None)

	trainer.train([], steps=3)
	checkpoint = trainer.create_checkpoint()

	restored = SolverTrainer(lambda samples: None)
	restored.restore_checkpoint(checkpoint)

	assert checkpoint.step == 3
	assert restored.current_step == 3
