from dataclasses import dataclass


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
	aggressive_actions: int = 0
	calls: int = 0
	showdowns: int = 0
	showdown_wins: int = 0

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
	def aggression_factor(self):
		return self.aggressive_actions / self.calls if self.calls else float(self.aggressive_actions)

	@property
	def wtsd(self):
		return self.showdowns / self.hands if self.hands else 0

	@property
	def wsd(self):
		return self.showdown_wins / self.showdowns if self.showdowns else 0
