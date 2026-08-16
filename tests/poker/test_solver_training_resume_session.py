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


def test_resume_session_training_delegates_after_restore():
	class TrainingCoordinator:
		def __init__(self):
			self.calls = []

		def train(self, samples, steps):
			self.calls.append((samples, steps))
			return "trained"

	coordinator = TrainingCoordinator()

	class Store:
		def restore_artifact(self, target):
			target.restored = True

	session = TrainingResumeSession(coordinator, Store())
	result = session.resume_training([1, 2], 5)

	assert result == "trained"
	assert coordinator.restored is True
	assert coordinator.calls == [([1, 2], 5)]
