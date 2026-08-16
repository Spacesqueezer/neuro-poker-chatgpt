from poker.solver.trainer_backend_state import TrainerBackendState


def test_backend_state_round_trip():
	state = TrainerBackendState(
		global_step=100,
		model_state={"weights": "snapshot"},
		optimizer_state={"lr": 0.001},
		scheduler_state={"epoch": 2},
	)

	restored = TrainerBackendState.from_payload(state.to_payload())

	assert restored.global_step == 100
	assert restored.model_state["weights"] == "snapshot"
	assert restored.optimizer_state["lr"] == 0.001
	assert restored.scheduler_state["epoch"] == 2
