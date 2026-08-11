from poker.statistics import MemoryStatisticsStorage, PlayerStatistics


def test_memory_statistics_storage():
	storage = MemoryStatisticsStorage()
	stats = PlayerStatistics(player_name="Player_001")

	storage.save(stats)

	assert storage.load("Player_001") == stats
