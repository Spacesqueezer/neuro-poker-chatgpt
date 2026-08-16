from poker.solver import SolverTrainer


class StatefulBackend:
	def __init__(self):
		self.saved = None

	def train_batch(self, batch):
		return None

	def save_state(self):
		return {"weights": 123}

	def load_state(self, state):
		self.saved = state


def test_checkpoint_contains_backend_state():
	backend = StatefulBackend()
	trainer = SolverTrainer(lambda samples: None, backend=backend)

	checkpoint = trainer.create_checkpoint()

	assert checkpoint.metadata["backend_state"] == {"weights": 123}


def test_restore_checkpoint_loads_backend_state():
	backend = StatefulBackend()
	trainer = SolverTrainer(lambda samples: None, backend=backend)

	trainer.restore_training_state({
		"current_step": 5,
		"backend_state": {"weights": 456},
	})

	assert trainer.current_step == 5
	assert backend.saved == {"weights": 456}
