from poker.statistics.database.repositories import (
	PlayerRepository,
	StatisticsRepository,
	AgentMemoryRepository,
)


class MemoryPlayerRepository(PlayerRepository):
	def __init__(self):
		self.players = {}

	def save(self, player):
		self.players[player.id] = player

	def get(self, player_id):
		return self.players.get(player_id)


class MemoryStatisticsRepository(StatisticsRepository):
	def __init__(self):
		self.statistics = {}

	def save(self, statistics):
		self.statistics[statistics.player_id] = statistics

	def get(self, player_id):
		return self.statistics.get(player_id)


class MemoryAgentMemoryRepository(AgentMemoryRepository):
	def __init__(self):
		self.memory = {}

	def save(self, memory):
		self.memory[(memory.agent_id, memory.player_id)] = memory

	def get(self, agent_id, player_id):
		return self.memory.get((agent_id, player_id))
