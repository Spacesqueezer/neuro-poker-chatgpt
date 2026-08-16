from poker.solver import SolverTrainer, TrainingCheckpointStore


def test_trainer_restore_checkpoint_integration(tmp_path):
	trainer = SolverTrainer(lambda samples: None)
	trainer.train([], steps=3)

	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")
	store.save(trainer.create_checkpoint())

	loaded = store.restore_into(trainer)

	assert loaded.step == 3
	assert trainer.current_step == 3
