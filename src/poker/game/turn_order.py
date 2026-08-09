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

	def next_active_player(self):
		if not self.players:
			return None

		for _ in range(len(self.players)):
			player = self.next_player()
			if not getattr(player, "folded", False):
				return player

		return None

	def set_position(self, position):
		if not self.players:
			self.position = 0
			return None

		self.position = position % len(self.players)
		return self.current_player()

	def set_to_next_active_after(self, position):
		if not self.players:
			return None

		self.position = position % len(self.players)
		return self.next_active_player()

	def reset(self):
		self.position = 0
