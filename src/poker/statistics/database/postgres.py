from dataclasses import dataclass


@dataclass
class PostgresConfig:
	url: str
	echo: bool = False


class PostgresSessionFactory:
	def __init__(self, config):
		self.config = config

	def create(self):
		return PostgresSession(self.config)


class PostgresSession:
	def __init__(self, config):
		self.config = config
		self.items = []

	def add(self, item):
		self.items.append(item)

	def commit(self):
		return True
