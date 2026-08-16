from dataclasses import dataclass

from poker.solver import TrainingRunCoordinator, TrainingRunState


@dataclass(frozen=True)
class FakeResult:
	steps: int


class FakeTrainer:
	def train(self, samples, steps=1):
		return FakeResult(steps=steps)


def test_training_run_state_updates_after_training():
	state = TrainingRunState(run_id="test")
	coordinator = TrainingRunCoordinator(FakeTrainer(), state=state)

	coordinator.train([], steps=3)

	assert coordinator.state.steps_completed == 3
	assert coordinator.state.run_id == "test"
	assert coordinator.state.created_at == state.created_at
