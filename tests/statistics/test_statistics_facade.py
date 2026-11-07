from poker.statistics.database import StatisticsFacade


class FakeService:
	def get_player_statistics(self, player_id):
		return player_id

	def get_agent_memory(self, agent_id, player_id):
		return (agent_id, player_id)


def test_statistics_facade_delegates_calls():
	facade = StatisticsFacade(FakeService())

	assert facade.get_player_statistics(1) == 1
	assert facade.get_opponent_memory("neural_a", 2) == ("neural_a", 2)
