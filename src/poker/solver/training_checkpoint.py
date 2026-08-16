from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class TrainingCheckpoint:
	step: int
	metadata: dict


def create_checkpoint(step, metadata=None):
	if step < 0:
		raise ValueError("step must be non-negative")

	return TrainingCheckpoint(
		step=step,
		metadata={} if metadata is None else dict(metadata),
	)


def restore_checkpoint(checkpoint):
	if not isinstance(checkpoint, TrainingCheckpoint):
		raise TypeError("invalid checkpoint")

	return checkpoint


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

	return create_checkpoint(
		step=data["step"],
		metadata=data["metadata"],
	)
