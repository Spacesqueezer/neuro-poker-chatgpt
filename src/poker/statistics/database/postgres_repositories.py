class PostgresPlayerRepository:
	def __init__(self, session):
		self.session = session

	def save(self, player):
		self.session.add(player)

	def get(self, player_id):
		return self.session.get(type(player_id), player_id)


class PostgresMemoryRepository:
	def __init__(self, session):
		self.session = session

	def save(self, memory):
		self.session.add(memory)

	def get(self, agent_id, player_id):
		raise NotImplementedError
