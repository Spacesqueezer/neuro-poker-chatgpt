from dataclasses import dataclass


@dataclass
class PostgresConfig:
	url: str
	echo: bool = False


class PostgresEngine:
	def __init__(self, config):
		self.config = config

	def create_session(self):
		return PostgresSession(self)


class PostgresSessionFactory:
	def __init__(self, config):
		self.engine = PostgresEngine(config)

	def create(self):
		return self.engine.create_session()


class PostgresSession:
	def __init__(self, engine):
		self.engine = engine
		self.items = []

	def add(self, item):
		self.items.append(item)

	def commit(self):
		return True
