class PostgresPlayerRepository:
	def __init__(self, session):
		self.session = session

	def save(self, player):
		self.session.add(player)


class PostgresMemoryRepository:
	def __init__(self, session):
		self.session = session

	def save_memory(self, memory):
		self.session.add(memory)
