class StatisticsFacade:
	def __init__(self, service):
		self.service = service

	def get_player_statistics(self, player_id):
		return self.service.get_player_statistics(player_id)

	def get_player_by_name(self, player_name):
		return self.service.get_player_by_name(player_name)

	def get_player_positions(self, player_id):
		return self.service.get_player_positions(player_id)

	def get_opponent_memory(self, agent_id, player_id):
		return self.service.get_agent_memory(agent_id, player_id)

	def save_opponent_memory(self, memory):
		return self.service.save_agent_memory(memory)
