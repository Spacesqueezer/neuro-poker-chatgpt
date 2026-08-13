from poker.game.positions import position_labels, positions_by_player
from poker.player.player import Player
from poker.statistics.collector import StatisticsCollector
from poker.statistics.database.memory import (
	MemoryAgentMemoryRepository,
	MemoryPlayerRepository,
	MemoryStatisticsRepository,
)
from poker.statistics.database.services import StatisticsService


def test_canonical_position_labels_cover_common_table_sizes():
	assert position_labels(2) == ("BTN/SB", "BB")
	assert position_labels(3) == ("BTN", "SB", "BB")
	assert position_labels(6) == ("BTN", "SB", "BB", "UTG", "HJ", "CO")
	assert position_labels(9)[-3:] == ("LJ", "HJ", "CO")


def test_positions_rotate_from_dealer_index():
	players = [
		Player("alice", 100),
		Player("bob", 100),
		Player("carol", 100),
		Player("dave", 100),
	]

	positions = positions_by_player(players, dealer_index=2)

	assert positions == {
		"carol": "BTN",
		"dave": "SB",
		"alice": "BB",
		"bob": "CO",
	}


def test_collector_tracks_position_splits():
	collector = StatisticsCollector()

	collector.register_hand(
		"alice",
		position="CO",
		entered_pot=True,
		raised_preflop=True,
		three_bet_opportunity=True,
		three_bet=True,
	)
	collector.register_hand(
		"alice",
		position="BTN",
		entered_pot=True,
	)
	collector.register_hand(
		"alice",
		position="CO",
		three_bet_opportunity=True,
	)

	alice = collector.get_player("alice")

	assert alice.positions["CO"].hands == 2
	assert alice.positions["CO"].vpip == 0.5
	assert alice.positions["CO"].pfr == 0.5
	assert alice.positions["CO"].three_bet == 0.5

	assert alice.positions["BTN"].hands == 1
	assert alice.positions["BTN"].vpip == 1.0


def test_service_persists_and_merges_position_splits():
	service = StatisticsService(
		MemoryPlayerRepository(),
		MemoryStatisticsRepository(),
		MemoryAgentMemoryRepository(),
	)

	first = StatisticsCollector()
	first.register_hand(
		"alice",
		position="CO",
		entered_pot=True,
		raised_preflop=True,
	)
	service.persist_collector(first)

	second = StatisticsCollector()
	second.register_hand(
		"alice",
		position="CO",
		three_bet_opportunity=True,
		three_bet=True,
	)
	service.persist_collector(second)

	player = service.player_repository.get_by_name("alice")
	position = service.statistics_repository.get_position(
		player.id,
		"CO",
	)

	assert position.hands == 2
	assert position.vpip_hands == 1
	assert position.vpip == 0.5
	assert position.pfr_hands == 1
	assert position.pfr == 0.5
	assert position.three_bet_opportunities == 1
	assert position.three_bets == 1
	assert position.three_bet == 1.0
