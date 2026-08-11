from poker.statistics.database.memory_adapter import (
	MemoryRepositoryAdapter,
)


class DummyRepository:
	def __init__(self):
		self.items = {}

	def save(self, value):
		self.items[0] = value

	def get(self, key):
		return self.items.get(0)


def test_memory_repository_adapter():
	repository = DummyRepository()

	adapter = MemoryRepositoryAdapter(
		repository,
		repository,
		repository,
	)

	adapter.save_player("player")

	assert adapter.get_player(1) == "player"
