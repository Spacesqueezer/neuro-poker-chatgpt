from poker.statistics.database.models import (
	PlayerRecord,
	PlayerStatisticsRecord,
	AgentMemoryRecord,
)


class PlayerRepository:
	def save(self, player: PlayerRecord):
		raise NotImplementedError

	def get(self, player_id: int):
		raise NotImplementedError

	def get_by_name(self, name: str):
		raise NotImplementedError

	def next_id(self):
		raise NotImplementedError


class StatisticsRepository:
	def save(self, statistics: PlayerStatisticsRecord):
		raise NotImplementedError

	def get(self, player_id: int):
		raise NotImplementedError


class AgentMemoryRepository:
	def save(self, memory: AgentMemoryRecord):
		raise NotImplementedError

	def get(self, agent_id: str, player_id: int):
		raise NotImplementedError
