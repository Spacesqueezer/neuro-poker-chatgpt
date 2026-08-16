from poker.solver.trainer_state import TrainerState
from poker.solver.training_checkpoint import create_checkpoint
from poker.solver.training_resume_session import TrainingResumeSession


class FakeStore:
	def __init__(self, checkpoint):
		self.checkpoint = checkpoint

	def restore_artifact(self, coordinator):
		return self.checkpoint


class FakeCoordinator:
	pass


def test_resume_session_exposes_restored_trainer_state():
	state = TrainerState(global_step=5, payload={"loss": 1})
	checkpoint = create_checkpoint(5, trainer_state=state)

	session = TrainingResumeSession(FakeCoordinator(), FakeStore(checkpoint))
	session.restore()

	assert session.trainer_state == state
