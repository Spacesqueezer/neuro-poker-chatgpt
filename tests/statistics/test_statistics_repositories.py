from poker.statistics.database import (
	PlayerRepository,
	StatisticsRepository,
	AgentMemoryRepository,
)


def test_repository_interfaces_exist():
	assert PlayerRepository
	assert StatisticsRepository
	assert AgentMemoryRepository
