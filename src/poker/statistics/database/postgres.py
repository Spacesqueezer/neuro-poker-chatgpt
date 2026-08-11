from dataclasses import dataclass


@dataclass
class PostgresConfig:
	url: str
	echo: bool = False


class PostgresEngine:
	def __init__(self, config):
		self.config = config


class PostgresSessionFactory:
	def __init__(self, config):
		self.engine = PostgresEngine(config)

	def create(self):
		return PostgresSession(self.engine)


class PostgresSession:
	def __init__(self, engine):
		self.engine = engine
		self.items = []

	def add(self, item):
		self.items.append(item)

	def commit(self):
		return True
