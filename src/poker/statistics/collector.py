from poker.statistics.player_stats import PlayerStatistics


class StatisticsCollector:
	def __init__(self):
		self.players = {}

	def get_player(self, player_name):
		if player_name not in self.players:
			self.players[player_name] = PlayerStatistics(
				player_name=player_name
			)

		return self.players[player_name]

	def register_hand(
		self,
		player_name,
		entered_pot=False,
		raised_preflop=False,
		three_bet=False,
		showdown=False,
		won_showdown=False,
	):
		stats = self.get_player(player_name)
		stats.hands += 1

		if entered_pot:
			stats.vpip_hands += 1

		if raised_preflop:
			stats.pfr_hands += 1

		if three_bet:
			stats.three_bets += 1

		if showdown:
			stats.showdowns += 1

		if won_showdown:
			stats.showdown_wins += 1

		return stats
