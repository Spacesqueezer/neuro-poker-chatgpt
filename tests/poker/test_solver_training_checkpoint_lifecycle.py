import pytest

from poker.solver import SolverTrainer, TrainingCheckpointStore


def test_trainer_checkpoint_store_save_and_resume(tmp_path):
	store = TrainingCheckpointStore(tmp_path / "checkpoint.json")
	trainer = SolverTrainer(lambda samples: None, checkpoint_store=store)
	trainer.train([], steps=3)

	saved = trainer.save_checkpoint()
	trainer.current_step = 0
	loaded = trainer.load_checkpoint()

	assert saved == loaded
	assert trainer.current_step == 3


def test_trainer_checkpoint_store_must_be_configured():
	trainer = SolverTrainer(lambda samples: None)

	with pytest.raises(ValueError, match="checkpoint store is not configured"):
		trainer.save_checkpoint()

	with pytest.raises(ValueError, match="checkpoint store is not configured"):
		trainer.load_checkpoint()
