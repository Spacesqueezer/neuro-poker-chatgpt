from pathlib import Path

from poker.solver.training_checkpoint import (
	deserialize_checkpoint,
	serialize_checkpoint,
)


class TrainingCheckpointStore:
	def __init__(self, path):
		self.path = Path(path)

	def save(self, checkpoint):
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.path.write_text(
			serialize_checkpoint(checkpoint),
			encoding="utf-8",
		)
		return self.path

	def load(self):
		payload = self.path.read_text(encoding="utf-8")
		return deserialize_checkpoint(payload)
