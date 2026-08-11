from dataclasses import dataclass


@dataclass
class MigrationConfig:
	database_url: str
	migration_path: str = "migrations"


class MigrationRegistry:
	def __init__(self):
		self.revisions = []

	def register(self, revision):
		self.revisions.append(revision)

	def latest(self):
		return self.revisions[-1] if self.revisions else None
