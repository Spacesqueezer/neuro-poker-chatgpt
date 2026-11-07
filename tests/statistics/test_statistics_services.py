from poker.statistics.database import (
	MemoryPlayerRepository,
	MemoryStatisticsRepository,
	MemoryAgentMemoryRepository,
	StatisticsService,
)


def test_statistics_service_reads_from_repositories():
	service = StatisticsService(
		MemoryPlayerRepository(),
		MemoryStatisticsRepository(),
		MemoryAgentMemoryRepository(),
	)

	assert service.get_player_statistics(1) is None
	assert service.get_agent_memory("neural_a", 1) is None
