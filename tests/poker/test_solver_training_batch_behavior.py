from poker.solver.training_batch import SolverTrainingBatch


def test_training_batch_accepts_valid_action_distribution():
	batch = SolverTrainingBatch(
		observations=((0.0, 1.0),),
		probabilities=((0.2, 0.2, 0.2, 0.2, 0.1, 0.1),),
	)

	batch.validate()


def test_training_batch_rejects_invalid_action_distribution_size():
	batch = SolverTrainingBatch(
		observations=((0.0, 1.0),),
		probabilities=((1.0,),),
	)

	try:
		batch.validate()
		raise AssertionError("validation should fail")
	except ValueError:
		pass
