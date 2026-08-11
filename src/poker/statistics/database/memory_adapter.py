class MemoryRepositoryAdapter:
	def __init__(self, player_repository, statistics_repository, memory_repository):
		self.player_repository = player_repository
		self.statistics_repository = statistics_repository
		self.memory_repository = memory_repository

	def save_player(self, player):
		self.player_repository.save(player)

	def get_player(self, player_id):
		return self.player_repository.get(player_id)

	def save_statistics(self, statistics):
		self.statistics_repository.save(statistics)

	def get_statistics(self, player_id):
		return self.statistics_repository.get(player_id)

	def save_memory(self, memory):
		self.memory_repository.save(memory)

	def get_memory(self, agent_id, player_id):
		return self.memory_repository.get(agent_id, player_id)
