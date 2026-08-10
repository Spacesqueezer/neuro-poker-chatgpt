from dataclasses import dataclass, field
import json
from pathlib import Path
import uuid


@dataclass(frozen=True)
class HandHistoryEvent:
	type: str
	data: dict

	def to_dict(self):
		return {"type": self.type, "data": self.data}

	@classmethod
	def from_dict(cls, payload):
		return cls(type=payload["type"], data=dict(payload.get("data", {})))


@dataclass
class HandHistory:
	hand_id: str | int
	players: list[dict]
	dealer: str
	small_blind: int
	big_blind: int
	events: list[HandHistoryEvent] = field(default_factory=list)
	final_stacks: dict[str, int] = field(default_factory=dict)
	result: str | None = None

	def add_event(self, event_type, **data):
		self.events.append(HandHistoryEvent(event_type, data))

	def finish(self, result, players):
		self.result = result
		self.final_stacks = {player.name: player.chips for player in players}

	def to_dict(self):
		return {
			"hand_id": self.hand_id,
			"players": self.players,
			"dealer": self.dealer,
			"small_blind": self.small_blind,
			"big_blind": self.big_blind,
			"events": [event.to_dict() for event in self.events],
			"final_stacks": self.final_stacks,
			"result": self.result,
		}

	@classmethod
	def from_dict(cls, payload):
		return cls(
			hand_id=payload["hand_id"],
			players=list(payload.get("players", [])),
			dealer=payload["dealer"],
			small_blind=payload["small_blind"],
			big_blind=payload["big_blind"],
			events=[HandHistoryEvent.from_dict(item) for item in payload.get("events", [])],
			final_stacks=dict(payload.get("final_stacks", {})),
			result=payload.get("result"),
		)


def create_hand_id():
	return uuid.uuid4().hex[:12]


class HandHistoryStore:
	def __init__(self, path):
		self.path = Path(path)

	def append(self, history):
		self.path.parent.mkdir(parents=True, exist_ok=True)
		with self.path.open("a", encoding="utf-8") as file:
			file.write(json.dumps(history.to_dict(), ensure_ascii=False) + "\n")

	def load_all(self):
		if not self.path.exists():
			return []

		histories = []
		with self.path.open("r", encoding="utf-8") as file:
			for line in file:
				line = line.strip()
				if line:
					histories.append(HandHistory.from_dict(json.loads(line)))
		return histories
