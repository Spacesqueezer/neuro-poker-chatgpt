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
		three_bet_opportunity=False,
		three_bet=False,
		fold_to_three_bet_opportunity=False,
		folded_to_three_bet=False,
		cbet_opportunity=False,
		cbet=False,
		aggressive_actions=0,
		calls=0,
		showdown=False,
		won_showdown=False,
		position=None,
	):
		stats = self.get_player(player_name)
		stats.hands += 1

		position_stats = (
			stats.get_position(position)
			if position is not None
			else None
		)
		if position_stats is not None:
			position_stats.hands += 1

		if entered_pot:
			stats.vpip_hands += 1
			if position_stats is not None:
				position_stats.vpip_hands += 1

		if raised_preflop:
			stats.pfr_hands += 1
			if position_stats is not None:
				position_stats.pfr_hands += 1

		if three_bet_opportunity:
			stats.three_bet_opportunities += 1
			if position_stats is not None:
				position_stats.three_bet_opportunities += 1

		if three_bet:
			stats.three_bets += 1
			if position_stats is not None:
				position_stats.three_bets += 1

		if fold_to_three_bet_opportunity:
			stats.fold_to_three_bet_opportunities += 1

		if folded_to_three_bet:
			stats.folds_to_three_bet += 1

		if cbet_opportunity:
			stats.cbet_opportunities += 1

		if cbet:
			stats.cbets += 1

		stats.aggressive_actions += aggressive_actions
		stats.calls += calls

		if showdown:
			stats.showdowns += 1

		if won_showdown:
			stats.showdown_wins += 1

		return stats
