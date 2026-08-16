from poker.solver.trainer_backend_state import TrainerBackendState
from poker.solver.training_checkpoint import TrainingCheckpoint
from poker.solver.training_run import TrainingRunCoordinator


class FakeTrainer:
	def __init__(self):
		self.backend_state = None

	def restore_checkpoint(self, checkpoint):
		self.backend_state = TrainerBackendState.from_payload(
			checkpoint.metadata["backend_state"]
		)


def test_coordinator_restore_preserves_backend_state():
	trainer = FakeTrainer()

	state = TrainerBackendState(
		global_step=100,
		model_state={"weight": 2},
	)

	checkpoint = TrainingCheckpoint(
		step=100,
		metadata={"backend_state": state.to_payload()},
	)

	coordinator = TrainingRunCoordinator(
		trainer=trainer,
	)

	coordinator.restore_checkpoint(checkpoint)

	assert coordinator.trainer.backend_state.global_step == 100
	assert coordinator.trainer.backend_state.model_state["weight"] == 2
