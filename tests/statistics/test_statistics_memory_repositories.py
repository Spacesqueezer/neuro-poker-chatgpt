from poker.statistics.database import (
	MemoryPlayerRepository,
	PlayerRecord,
)


def test_memory_player_repository():
	repository = MemoryPlayerRepository()
	player = PlayerRecord(id=1, name="Player_001")

	repository.save(player)

	assert repository.get(1) == player
