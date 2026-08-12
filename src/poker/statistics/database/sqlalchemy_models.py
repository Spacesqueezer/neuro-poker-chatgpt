from dataclasses import dataclass


class BaseModel:
	pass


@dataclass
class PlayerModel(BaseModel):
	id: int
	name: str
	profile_id: int | None = None


@dataclass
class PlayerStatisticsModel(BaseModel):
	player_id: int
	hands: int = 0
	vpip: float = 0.0
	pfr: float = 0.0
	three_bet: float = 0.0
	aggression: float = 0.0
	wtsd: float = 0.0
	wsd: float = 0.0


@dataclass
class AgentMemoryModel(BaseModel):
	agent_id: str
	player_id: int
	hands_observed: int = 0
	vpip_estimate: float = 0.0
	pfr_estimate: float = 0.0
	aggression_estimate: float = 0.0
	confidence: float = 0.0
