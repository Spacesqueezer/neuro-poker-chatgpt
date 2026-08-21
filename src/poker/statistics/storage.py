

class StatisticsStorage:
	def save(self, statistics):
		raise NotImplementedError

	def load(self, player_name):
		raise NotImplementedError


class MemoryStatisticsStorage(StatisticsStorage):
	def __init__(self):
		self.players = {}

	def save(self, statistics):
		self.players[statistics.player_name] = statistics

	def load(self, player_name):
		return self.players.get(player_name)
