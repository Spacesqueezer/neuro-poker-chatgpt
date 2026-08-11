from dataclasses import dataclass, field


@dataclass
class PlayerRecord:
	id: int
	name: str
	profile_id: int | None = None


@dataclass
class PlayerStatisticsRecord:
	player_id: int
	hands: int = 0
	vpip: float = 0.0
	pfr: float = 0.0
	three_bet: float = 0.0
	aggression: float = 0.0
	wtsd: float = 0.0
	wsd: float = 0.0


@dataclass
class AgentMemoryRecord:
	agent_id: str
	player_id: int
	hands_observed: int = 0
	vpip_estimate: float = 0.0
	pfr_estimate: float = 0.0
	aggression_estimate: float = 0.0
	confidence: float = 0.0
