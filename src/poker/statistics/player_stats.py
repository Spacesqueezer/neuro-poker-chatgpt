from dataclasses import dataclass, field


@dataclass
class PositionStatistics:
	position: str
	hands: int = 0
	vpip_hands: int = 0
	pfr_hands: int = 0
	three_bet_opportunities: int = 0
	three_bets: int = 0

	@property
	def vpip(self):
		return self.vpip_hands / self.hands if self.hands else 0

	@property
	def pfr(self):
		return self.pfr_hands / self.hands if self.hands else 0

	@property
	def three_bet(self):
		return (
			self.three_bets / self.three_bet_opportunities
			if self.three_bet_opportunities
			else 0
		)


@dataclass
class PlayerStatistics:
	player_name: str
	hands: int = 0
	vpip_hands: int = 0
	pfr_hands: int = 0
	three_bet_opportunities: int = 0
	three_bets: int = 0
	fold_to_three_bet_opportunities: int = 0
	folds_to_three_bet: int = 0
	cbet_opportunities: int = 0
	cbets: int = 0
	fold_to_cbet_opportunities: int = 0
	folds_to_cbet: int = 0
	aggressive_actions: int = 0
	calls: int = 0
	flop_aggressive_actions: int = 0
	flop_calls: int = 0
	turn_aggressive_actions: int = 0
	turn_calls: int = 0
	river_aggressive_actions: int = 0
	river_calls: int = 0
	showdowns: int = 0
	showdown_wins: int = 0
	positions: dict[str, PositionStatistics] = field(default_factory=dict)

	def get_position(self, position):
		if position not in self.positions:
			self.positions[position] = PositionStatistics(position=position)

		return self.positions[position]

	@property
	def vpip(self):
		return self.vpip_hands / self.hands if self.hands else 0

	@property
	def pfr(self):
		return self.pfr_hands / self.hands if self.hands else 0

	@property
	def three_bet(self):
		return (
			self.three_bets / self.three_bet_opportunities
			if self.three_bet_opportunities
			else 0
		)

	@property
	def fold_to_three_bet(self):
		return (
			self.folds_to_three_bet / self.fold_to_three_bet_opportunities
			if self.fold_to_three_bet_opportunities
			else 0
		)

	@property
	def cbet(self):
		return self.cbets / self.cbet_opportunities if self.cbet_opportunities else 0

	@property
	def fold_to_cbet(self):
		return (
			self.folds_to_cbet / self.fold_to_cbet_opportunities
			if self.fold_to_cbet_opportunities
			else 0
		)

	@property
	def aggression_factor(self):
		return self._aggression_factor(
			self.aggressive_actions,
			self.calls,
		)

	@property
	def flop_aggression_factor(self):
		return self._aggression_factor(
			self.flop_aggressive_actions,
			self.flop_calls,
		)

	@property
	def turn_aggression_factor(self):
		return self._aggression_factor(
			self.turn_aggressive_actions,
			self.turn_calls,
		)

	@property
	def river_aggression_factor(self):
		return self._aggression_factor(
			self.river_aggressive_actions,
			self.river_calls,
		)

	def _aggression_factor(self, aggressive_actions, calls):
		return aggressive_actions / calls if calls else float(aggressive_actions)

	@property
	def wtsd(self):
		return self.showdowns / self.hands if self.hands else 0

	@property
	def wsd(self):
		return self.showdown_wins / self.showdowns if self.showdowns else 0
