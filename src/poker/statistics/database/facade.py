class StatisticsFacade:
	def __init__(self, service):
		self.service = service

	def get_player_statistics(self, player_id):
		return self.service.get_player_statistics(player_id)

	def get_opponent_memory(self, agent_id, player_id):
		return self.service.get_agent_memory(agent_id, player_id)
