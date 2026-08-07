class TurnOrder:
	def __init__(self, players=None):
		self.players = list(players or [])
		self.position = 0

	def current_player(self):
		if not self.players:
			return None

		return self.players[self.position]

	def next_player(self):
		if not self.players:
			return None

		self.position = (self.position + 1) % len(self.players)
		return self.current_player()

	def reset(self):
		self.position = 0
