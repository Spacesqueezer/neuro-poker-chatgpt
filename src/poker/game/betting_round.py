class BettingRound:
	def __init__(self, players):
		self.players = players
		self.acted_players = set()

	def mark_action(self, player, bet_increased=False):
		if bet_increased:
			self.acted_players = {player}
			return

		self.acted_players.add(player)

	def active_players(self):
		return [player for player in self.players if not getattr(player, "folded", False)]

	def is_complete(self):
		active_players = self.active_players()

		if not active_players:
			return False

		if len(active_players) == 1:
			return True

		target_bet = max(player.current_bet for player in active_players)

		return all(
			player in self.acted_players and player.current_bet == target_bet
			for player in active_players
		)

	def reset(self):
		self.acted_players.clear()
