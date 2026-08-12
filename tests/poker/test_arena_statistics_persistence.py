from poker.agents import CallingStationAgent, NitAgent
from poker.arena.runner import ArenaRunner
from poker.statistics.database.memory import (
	MemoryAgentMemoryRepository,
	MemoryPlayerRepository,
	MemoryStatisticsRepository,
)
from poker.statistics.database.services import StatisticsService


def _service():
	return StatisticsService(
		MemoryPlayerRepository(),
		MemoryStatisticsRepository(),
		MemoryAgentMemoryRepository(),
	)


def test_arena_collects_successful_hand_statistics_automatically():
	runner = ArenaRunner(
		{
			"calling": CallingStationAgent(),
			"nit": NitAgent(),
		},
		starting_stack=100,
	)

	stats = runner.run(
		hands=20,
		seed=42,
	)

	collector = runner.last_statistics_collector

	assert stats.hands > 0
	assert collector is not None
	assert collector.get_player("calling").hands == stats.hands
	assert collector.get_player("nit").hands == stats.hands


def test_arena_persists_tracker_statistics_by_stable_player_id():
	service = _service()
	runner = ArenaRunner(
		{
			"calling": CallingStationAgent(),
			"nit": NitAgent(),
		},
		starting_stack=100,
		statistics_service=service,
		player_ids={
			"calling": 101,
			"nit": 202,
		},
	)

	stats = runner.run(
		hands=20,
		seed=42,
	)

	calling = service.get_player_statistics(101)
	nit = service.get_player_statistics(202)

	assert calling is not None
	assert nit is not None
	assert calling.hands == stats.hands
	assert nit.hands == stats.hands


def test_arena_persistence_accumulates_across_runs():
	service = _service()
	runner = ArenaRunner(
		{
			"calling": CallingStationAgent(),
			"nit": NitAgent(),
		},
		starting_stack=100,
		statistics_service=service,
		player_ids={
			"calling": 101,
			"nit": 202,
		},
	)

	first = runner.run(
		hands=10,
		seed=42,
	)
	second = runner.run(
		hands=10,
		seed=142,
	)

	assert service.get_player_statistics(101).hands == (
		first.hands + second.hands
	)
	assert service.get_player_statistics(202).hands == (
		first.hands + second.hands
	)


def test_arena_requires_stable_ids_when_persistence_is_enabled():
	service = _service()

	try:
		ArenaRunner(
			{
				"calling": CallingStationAgent(),
				"nit": NitAgent(),
			},
			statistics_service=service,
		)
	except ValueError as error:
		assert "player_ids are required" in str(error)
	else:
		raise AssertionError("Expected stable player id validation")
