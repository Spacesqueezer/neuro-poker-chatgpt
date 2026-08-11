class StatisticsService:
	def __init__(
		self,
		player_repository,
		statistics_repository,
		memory_repository,
	):
		self.player_repository = player_repository
		self.statistics_repository = statistics_repository
		self.memory_repository = memory_repository

	def get_player_statistics(self, player_id):
		return self.statistics_repository.get(player_id)

	def get_agent_memory(self, agent_id, player_id):
		return self.memory_repository.get(agent_id, player_id)
