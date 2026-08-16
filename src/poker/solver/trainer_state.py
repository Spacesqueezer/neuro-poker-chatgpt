from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrainerState:
	global_step: int
	payload: dict[str, Any]

	def serialize(self) -> dict[str, Any]:
		return {
			"global_step": self.global_step,
			"payload": dict(self.payload),
		}

	@classmethod
	def deserialize(cls, data: dict[str, Any]) -> "TrainerState":
		return cls(
			global_step=int(data["global_step"]),
			payload=dict(data["payload"]),
		)
