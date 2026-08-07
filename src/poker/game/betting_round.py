class BettingRound:
	def __init__(self, players):
		self.players = players
		self.acted_players = set()

	def mark_action(self, player):
		self.acted_players.add(player)

	def is_complete(self):
		active_players = [
			player for player in self.players
			if not getattr(player, "folded", False)
		]

		return bool(active_players) and all(
			player in self.acted_players
			for player in active_players
		)

	def reset(self):
		self.acted_players.clear()
