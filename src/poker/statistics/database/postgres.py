from dataclasses import dataclass


@dataclass
class PostgresConfig:
	url: str


class PostgresSession:
	def __init__(self, config):
		self.config = config

	def add(self, item):
		raise NotImplementedError

	def commit(self):
		raise NotImplementedError
