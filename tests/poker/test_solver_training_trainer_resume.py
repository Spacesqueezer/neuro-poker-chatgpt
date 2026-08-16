from poker.solver import SolverTrainer


class ResumeBackend:
	def __init__(self):
		self.state = None

	def train_batch(self, batch):
		return None

	def save_state(self):
		return {"step": 10}

	def load_state(self, state):
		self.state = state


def test_resume_round_trip_restores_backend_state():
	backend = ResumeBackend()
	trainer = SolverTrainer(lambda samples: None, backend=backend)

	checkpoint = trainer.create_checkpoint()
	trainer.current_step = 0
	trainer.restore_checkpoint(checkpoint)

	assert trainer.current_step == checkpoint.step
	assert backend.state == {"step": 10}
