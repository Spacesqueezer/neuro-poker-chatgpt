from poker.solver.training_resume_session import TrainingResumeSession


class FakeStore:
	def restore_artifact(self, coordinator):
		coordinator.restored = True
		return coordinator


class FakeCoordinator:
	pass


def test_resume_session_restores_artifact():
	coordinator = FakeCoordinator()
	session = TrainingResumeSession(coordinator, FakeStore())

	result = session.resume()

	assert result is coordinator
	assert coordinator.restored is True
