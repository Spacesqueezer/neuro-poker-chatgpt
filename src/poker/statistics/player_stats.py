from dataclasses import dataclass


@dataclass
class PlayerStatistics:
	player_name: str
	hands: int = 0
	vpip_hands: int = 0
	pfr_hands: int = 0
	three_bets: int = 0
	showdowns: int = 0
	showdown_wins: int = 0

	@property
	def vpip(self):
		return self.vpip_hands / self.hands if self.hands else 0

	@property
	def pfr(self):
		return self.pfr_hands / self.hands if self.hands else 0

	@property
	def wtsd(self):
		return self.showdowns / self.hands if self.hands else 0

	@property
	def wsd(self):
		return self.showdown_wins / self.showdowns if self.showdowns else 0
