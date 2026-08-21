from poker.statistics.database.repositories import (
	AgentMemoryRepository,
	PlayerRepository,
	StatisticsRepository,
)


class MemoryPlayerRepository(PlayerRepository):
	def __init__(self):
		self.players = {}

	def save(self, player):
		existing = self.get_by_name(player.name)
		if existing is not None and existing.id != player.id:
			raise ValueError(f"Player name already exists: {player.name}")

		self.players[player.id] = player

	def get(self, player_id):
		return self.players.get(player_id)

	def get_by_name(self, name):
		for player in self.players.values():
			if player.name == name:
				return player

		return None

	def next_id(self):
		return max(self.players, default=0) + 1


class MemoryStatisticsRepository(StatisticsRepository):
	def __init__(self):
		self.statistics = {}
		self.position_statistics = {}

	def save(self, statistics):
		self.statistics[statistics.player_id] = statistics

	def get(self, player_id):
		return self.statistics.get(player_id)

	def save_position(self, statistics):
		self.position_statistics[
			(statistics.player_id, statistics.position)
		] = statistics

	def get_position(self, player_id, position):
		return self.position_statistics.get((player_id, position))

	def list_positions(self, player_id):
		return [
			record
			for (stored_player_id, _), record in self.position_statistics.items()
			if stored_player_id == player_id
		]


class MemoryAgentMemoryRepository(AgentMemoryRepository):
	def __init__(self):
		self.memory = {}

	def save(self, memory):
		self.memory[(memory.agent_id, memory.player_id)] = memory

	def get(self, agent_id, player_id):
		return self.memory.get((agent_id, player_id))
