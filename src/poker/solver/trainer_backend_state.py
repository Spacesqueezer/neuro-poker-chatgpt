from dataclasses import dataclass
from typing import Any


@dataclass
class TrainerBackendState:
	global_step: int
	model_state: dict[str, Any]
	optimizer_state: dict[str, Any] | None = None
	scheduler_state: dict[str, Any] | None = None

	def to_payload(self) -> dict[str, Any]:
		return {
			"global_step": self.global_step,
			"model_state": self.model_state,
			"optimizer_state": self.optimizer_state,
			"scheduler_state": self.scheduler_state,
		}

	@classmethod
	def from_payload(cls, payload: dict[str, Any]) -> "TrainerBackendState":
		return cls(
			global_step=int(payload["global_step"]),
			model_state=dict(payload.get("model_state", {})),
			optimizer_state=payload.get("optimizer_state"),
			scheduler_state=payload.get("scheduler_state"),
		)
