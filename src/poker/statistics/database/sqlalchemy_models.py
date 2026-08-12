from dataclasses import dataclass


class DeclarativeBase:
	metadata = {}


class MappedField:
	def __init__(self, name, primary_key=False):
		self.name = name
		self.primary_key = primary_key


@dataclass
class PlayerModel(DeclarativeBase):
	id: int
	name: str
	profile_id: int | None = None

	__mapped_fields__ = {
		"id": MappedField("id", primary_key=True),
		"name": MappedField("name"),
		"profile_id": MappedField("profile_id"),
	}


@dataclass
class PlayerStatisticsModel(DeclarativeBase):
	player_id: int
	hands: int = 0
	vpip: float = 0.0
	pfr: float = 0.0
	three_bet: float = 0.0
	aggression: float = 0.0
	wtsd: float = 0.0
	wsd: float = 0.0

	__mapped_fields__ = {
		"player_id": MappedField("player_id", primary_key=True),
	}


@dataclass
class AgentMemoryModel(DeclarativeBase):
	agent_id: str
	player_id: int
	hands_observed: int = 0
	vpip_estimate: float = 0.0
	pfr_estimate: float = 0.0
	aggression_estimate: float = 0.0
	confidence: float = 0.0

	__mapped_fields__ = {
		"agent_id": MappedField("agent_id", primary_key=True),
		"player_id": MappedField("player_id", primary_key=True),
	}
