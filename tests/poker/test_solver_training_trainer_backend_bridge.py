from poker.solver import SolverTrainer


class RecordingBackend:
	def __init__(self):
		self.batches = []

	def train_batch(self, batch):
		self.batches.append(batch)
		return {"status": "accepted"}


def test_solver_trainer_delegates_steps_to_backend():
	backend = RecordingBackend()
	trainer = SolverTrainer(lambda samples: None, backend=backend)
	batch = object()

	result = trainer.train(batch, steps=2)

	assert backend.batches == [batch, batch]
	assert result.steps == 2
	assert trainer.current_step == 2


def test_solver_trainer_preserves_objective_only_behavior_without_backend():
	calls = []
	trainer = SolverTrainer(lambda samples: calls.append(samples))
	batch = object()

	trainer.train(batch, steps=2)

	assert calls == [batch, batch]
