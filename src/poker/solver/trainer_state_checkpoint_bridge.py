from .trainer_state import TrainerState


TRAINER_STATE_METADATA_KEY = "trainer_state"


def attach_trainer_state(metadata: dict, state: TrainerState) -> dict:
	result = dict(metadata)
	result[TRAINER_STATE_METADATA_KEY] = state.serialize()
	return result


def extract_trainer_state(metadata: dict) -> TrainerState | None:
	payload = metadata.get(TRAINER_STATE_METADATA_KEY)
	if payload is None:
		return None

	return TrainerState.deserialize(payload)
