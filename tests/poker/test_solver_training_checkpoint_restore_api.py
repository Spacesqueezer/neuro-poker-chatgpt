from poker.solver import SolverTrainer, TrainingCheckpointStore


def test_checkpoint_store_restores_into_trainer(tmp_path):
	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")
	source = SolverTrainer(lambda samples: None)
	source.train([], steps=4)
	store.save(source.create_checkpoint())

	target = SolverTrainer(lambda samples: None)
	checkpoint = store.restore_into(target)

	assert checkpoint.step == 4
	assert target.current_step == 4
