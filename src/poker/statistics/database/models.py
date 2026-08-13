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
	vpip_hands: int = 0
	pfr_hands: int = 0
	three_bet_opportunities: int = 0
	three_bets: int = 0
	fold_to_three_bet_opportunities: int = 0
	folds_to_three_bet: int = 0
	cbet_opportunities: int = 0
	cbets: int = 0
	aggressive_actions: int = 0
	calls: int = 0
	showdowns: int = 0
	showdown_wins: int = 0


@dataclass
class PlayerPositionStatisticsRecord:
	player_id: int
	position: str
	hands: int = 0
	vpip: float = 0.0
	pfr: float = 0.0
	three_bet: float = 0.0
	vpip_hands: int = 0
	pfr_hands: int = 0
	three_bet_opportunities: int = 0
	three_bets: int = 0


@dataclass
class AgentMemoryRecord:
	agent_id: str
	player_id: int
	hands_observed: int = 0
	vpip_estimate: float = 0.0
	pfr_estimate: float = 0.0
	aggression_estimate: float = 0.0
	confidence: float = 0.0
