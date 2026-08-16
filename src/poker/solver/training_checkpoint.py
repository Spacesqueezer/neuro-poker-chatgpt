from dataclasses import dataclass


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
