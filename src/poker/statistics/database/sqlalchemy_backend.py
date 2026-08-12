from dataclasses import dataclass


@dataclass
class SQLAlchemyConfig:
	url: str
	echo: bool = False


class SQLAlchemyEngine:
	def __init__(self, config):
		self.config = config

	def create_session(self):
		return SQLAlchemySession(self)


class SQLAlchemySession:
	def __init__(self, engine):
		self.engine = engine
		self.items = []

	def add(self, item):
		self.items.append(item)

	def commit(self):
		return True

	def rollback(self):
		self.items.clear()
