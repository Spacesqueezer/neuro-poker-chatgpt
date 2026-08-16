from dataclasses import asdict, dataclass
import json

from .trainer_state import TrainerState
from .trainer_state_checkpoint_bridge import attach_trainer_state, extract_trainer_state


@dataclass(frozen=True)
class TrainingCheckpoint:
	step: int
	metadata: dict


def create_checkpoint(step, metadata=None, trainer_state=None):
	if step < 0:
		raise ValueError("step must be non-negative")

	checkpoint_metadata = {} if metadata is None else dict(metadata)
	if trainer_state is not None:
		checkpoint_metadata = attach_trainer_state(checkpoint_metadata, trainer_state)

	return TrainingCheckpoint(
		step=step,
		metadata=checkpoint_metadata,
	)


def restore_checkpoint(checkpoint):
	if not isinstance(checkpoint, TrainingCheckpoint):
		raise TypeError("invalid checkpoint")

	return checkpoint


def extract_checkpoint_trainer_state(checkpoint):
	if not isinstance(checkpoint, TrainingCheckpoint):
		raise TypeError("invalid checkpoint")

	return extract_trainer_state(checkpoint.metadata)


def serialize_checkpoint(checkpoint):
	if not isinstance(checkpoint, TrainingCheckpoint):
		raise TypeError("invalid checkpoint")

	return json.dumps(
		asdict(checkpoint),
		sort_keys=True,
		separators=(",", ":"),
	)


def deserialize_checkpoint(payload):
	data = json.loads(payload)

	if not isinstance(data, dict):
		raise ValueError("checkpoint payload must be an object")
	if set(data) != {"step", "metadata"}:
		raise ValueError("checkpoint payload fields are invalid")
	if not isinstance(data["step"], int) or data["step"] < 0:
		raise ValueError("step must be non-negative")
	if not isinstance(data["metadata"], dict):
		raise ValueError("checkpoint metadata is invalid")

	return create_checkpoint(
		step=data["step"],
		metadata=data["metadata"],
	)
