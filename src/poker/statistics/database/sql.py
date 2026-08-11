from dataclasses import dataclass


@dataclass
class DatabaseConfig:
	url: str


class DatabaseSessionFactory:
	def __init__(self, config):
		self.config = config

	def create_session(self):
		raise NotImplementedError(
			"SQLAlchemy session is not configured yet"
		)
