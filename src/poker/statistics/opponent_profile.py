from dataclasses import dataclass, field


@dataclass(frozen=True)
class PositionProfile:
	position: str
	hands: int
	vpip: float
	pfr: float
	three_bet: float


@dataclass(frozen=True)
class AgentMemoryProfile:
	hands_observed: int = 0
	vpip_estimate: float = 0.0
	pfr_estimate: float = 0.0
	aggression_estimate: float = 0.0
	confidence: float = 0.0


@dataclass(frozen=True)
class OpponentProfile:
	player_id: int
	name: str
	hands: int = 0
	vpip: float = 0.0
	pfr: float = 0.0
	three_bet: float = 0.0
	fold_to_three_bet: float = 0.0
	cbet: float = 0.0
	fold_to_cbet: float = 0.0
	aggression: float = 0.0
	flop_aggression: float = 0.0
	turn_aggression: float = 0.0
	river_aggression: float = 0.0
	wtsd: float = 0.0
	wsd: float = 0.0
	positions: tuple[PositionProfile, ...] = ()
	memory: AgentMemoryProfile = field(default_factory=AgentMemoryProfile)

	def position(self, position):
		for profile in self.positions:
			if profile.position == position:
				return profile

		return None


class OpponentProfileProvider:
	def __init__(self, statistics_facade):
		self.statistics = statistics_facade

	def get(self, player_name, agent_id=None):
		player = self.statistics.get_player_by_name(player_name)
		if player is None:
			return None

		statistics = self.statistics.get_player_statistics(player.id)
		positions = tuple(
			PositionProfile(
				position=record.position,
				hands=record.hands,
				vpip=record.vpip,
				pfr=record.pfr,
				three_bet=record.three_bet,
			)
			for record in sorted(
				self.statistics.get_player_positions(player.id),
				key=lambda item: item.position,
			)
		)

		memory = None
		if agent_id is not None:
			memory = self.statistics.get_opponent_memory(
				agent_id,
				player.id,
			)

		return OpponentProfile(
			player_id=player.id,
			name=player.name,
			hands=statistics.hands if statistics is not None else 0,
			vpip=statistics.vpip if statistics is not None else 0.0,
			pfr=statistics.pfr if statistics is not None else 0.0,
			three_bet=statistics.three_bet if statistics is not None else 0.0,
			fold_to_three_bet=self._ratio(
				statistics.folds_to_three_bet if statistics is not None else 0,
				statistics.fold_to_three_bet_opportunities
				if statistics is not None
				else 0,
			),
			cbet=self._ratio(
				statistics.cbets if statistics is not None else 0,
				statistics.cbet_opportunities if statistics is not None else 0,
			),
			fold_to_cbet=self._ratio(
				statistics.folds_to_cbet if statistics is not None else 0,
				statistics.fold_to_cbet_opportunities
				if statistics is not None
				else 0,
			),
			aggression=statistics.aggression if statistics is not None else 0.0,
			flop_aggression=self._aggression(
				statistics.flop_aggressive_actions
				if statistics is not None
				else 0,
				statistics.flop_calls if statistics is not None else 0,
			),
			turn_aggression=self._aggression(
				statistics.turn_aggressive_actions
				if statistics is not None
				else 0,
				statistics.turn_calls if statistics is not None else 0,
			),
			river_aggression=self._aggression(
				statistics.river_aggressive_actions
				if statistics is not None
				else 0,
				statistics.river_calls if statistics is not None else 0,
			),
			wtsd=statistics.wtsd if statistics is not None else 0.0,
			wsd=statistics.wsd if statistics is not None else 0.0,
			positions=positions,
			memory=self._memory_profile(memory),
		)

	def _memory_profile(self, memory):
		if memory is None:
			return AgentMemoryProfile()

		return AgentMemoryProfile(
			hands_observed=memory.hands_observed,
			vpip_estimate=memory.vpip_estimate,
			pfr_estimate=memory.pfr_estimate,
			aggression_estimate=memory.aggression_estimate,
			confidence=memory.confidence,
		)

	def _ratio(self, numerator, denominator):
		return numerator / denominator if denominator else 0.0

	def _aggression(self, aggressive_actions, calls):
		return (
			aggressive_actions / calls
			if calls
			else float(aggressive_actions)
		)


class OpponentProfileEncoder:
	FEATURE_NAMES = (
		"hands",
		"vpip",
		"pfr",
		"three_bet",
		"fold_to_three_bet",
		"cbet",
		"fold_to_cbet",
		"aggression",
		"flop_aggression",
		"turn_aggression",
		"river_aggression",
		"wtsd",
		"wsd",
		"position_hands",
		"position_vpip",
		"position_pfr",
		"position_three_bet",
		"memory_hands_observed",
		"memory_vpip",
		"memory_pfr",
		"memory_aggression",
		"memory_confidence",
	)

	def encode(self, profile, position=None):
		position_profile = (
			profile.position(position)
			if position is not None
			else None
		)
		memory = profile.memory

		return (
			float(profile.hands),
			profile.vpip,
			profile.pfr,
			profile.three_bet,
			profile.fold_to_three_bet,
			profile.cbet,
			profile.fold_to_cbet,
			profile.aggression,
			profile.flop_aggression,
			profile.turn_aggression,
			profile.river_aggression,
			profile.wtsd,
			profile.wsd,
			float(position_profile.hands) if position_profile else 0.0,
			position_profile.vpip if position_profile else 0.0,
			position_profile.pfr if position_profile else 0.0,
			position_profile.three_bet if position_profile else 0.0,
			float(memory.hands_observed),
			memory.vpip_estimate,
			memory.pfr_estimate,
			memory.aggression_estimate,
			memory.confidence,
		)

	@property
	def size(self):
		return len(self.FEATURE_NAMES)
