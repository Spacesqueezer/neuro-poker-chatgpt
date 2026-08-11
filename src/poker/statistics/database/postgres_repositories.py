from poker.statistics.database.repositories import (
	PlayerRepository,
	AgentMemoryRepository,
)


class PostgresPlayerRepository(PlayerRepository):
	def __init__(self, session):
		self.session = session

	def save(self, player):
		self.session.add(player)

	def get(self, player_id):
		return self.session.get(player_id)


class PostgresMemoryRepository(AgentMemoryRepository):
	def __init__(self, session):
		self.session = session

	def save(self, memory):
		self.session.add(memory)

	def get(self, agent_id, player_id):
		return self.session.get((agent_id, player_id))
