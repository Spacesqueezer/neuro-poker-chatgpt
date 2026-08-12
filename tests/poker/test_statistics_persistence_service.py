import pytest

from poker.statistics.collector import StatisticsCollector
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


def test_service_persists_collector_counters_and_rates():
	collector = StatisticsCollector()

	collector.register_hand(
		"alice",
		entered_pot=True,
		raised_preflop=True,
		three_bet_opportunity=True,
		three_bet=True,
		cbet_opportunity=True,
		cbet=True,
		aggressive_actions=2,
		calls=1,
		showdown=True,
		won_showdown=True,
	)
	collector.register_hand(
		"alice",
		entered_pot=False,
		raised_preflop=False,
		three_bet_opportunity=True,
		fold_to_three_bet_opportunity=True,
		folded_to_three_bet=True,
		aggressive_actions=1,
		calls=2,
	)

	service = _service()
	records = service.persist_collector(
		collector,
		{"alice": 101},
	)

	assert len(records) == 1

	record = service.get_player_statistics(101)

	assert record.player_id == 101
	assert record.hands == 2
	assert record.vpip_hands == 1
	assert record.vpip == 0.5
	assert record.pfr_hands == 1
	assert record.pfr == 0.5
	assert record.three_bet_opportunities == 2
	assert record.three_bets == 1
	assert record.three_bet == 0.5
	assert record.fold_to_three_bet_opportunities == 1
	assert record.folds_to_three_bet == 1
	assert record.cbet_opportunities == 1
	assert record.cbets == 1
	assert record.aggressive_actions == 3
	assert record.calls == 3
	assert record.aggression == 1.0
	assert record.showdowns == 1
	assert record.showdown_wins == 1
	assert record.wtsd == 0.5
	assert record.wsd == 1.0


def test_service_persists_multiple_players_by_stable_id():
	collector = StatisticsCollector()
	collector.register_hand("alice", entered_pot=True)
	collector.register_hand("bob", raised_preflop=True)

	service = _service()
	service.persist_collector(
		collector,
		{
			"alice": 101,
			"bob": 202,
		},
	)

	assert service.get_player_statistics(101).vpip_hands == 1
	assert service.get_player_statistics(202).pfr_hands == 1


def test_service_merges_new_session_counters_with_existing_history():
	service = _service()

	first = StatisticsCollector()
	first.register_hand(
		"alice",
		entered_pot=True,
		raised_preflop=True,
		three_bet_opportunity=True,
		three_bet=True,
		aggressive_actions=2,
		calls=1,
	)
	service.persist_collector(first, {"alice": 101})

	second = StatisticsCollector()
	second.register_hand(
		"alice",
		three_bet_opportunity=True,
		fold_to_three_bet_opportunity=True,
		folded_to_three_bet=True,
		aggressive_actions=1,
		calls=2,
	)
	service.persist_collector(second, {"alice": 101})

	record = service.get_player_statistics(101)

	assert record.hands == 2
	assert record.vpip_hands == 1
	assert record.vpip == 0.5
	assert record.pfr_hands == 1
	assert record.pfr == 0.5
	assert record.three_bet_opportunities == 2
	assert record.three_bets == 1
	assert record.three_bet == 0.5
	assert record.fold_to_three_bet_opportunities == 1
	assert record.folds_to_three_bet == 1
	assert record.aggressive_actions == 3
	assert record.calls == 3
	assert record.aggression == 1.0


def test_service_rejects_collector_player_without_persistent_id():
	collector = StatisticsCollector()
	collector.register_hand("unknown", entered_pot=True)

	service = _service()

	with pytest.raises(
		KeyError,
		match="Missing persistent player id for unknown",
	):
		service.persist_collector(
			collector,
			{},
		)
