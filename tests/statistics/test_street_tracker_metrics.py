from poker.game.hand_history import HandHistory
from poker.statistics.hand_adapter import HandStatisticsAdapter
from poker.statistics.database.memory import (
	MemoryAgentMemoryRepository,
	MemoryPlayerRepository,
	MemoryStatisticsRepository,
)
from poker.statistics.database.services import StatisticsService


def _history(actions):
	history = HandHistory(
		hand_id="street-tracker",
		players=[
			{"name": "alice", "starting_chips": 100},
			{"name": "bob", "starting_chips": 100},
			{"name": "carol", "starting_chips": 100},
		],
		dealer="alice",
		small_blind=1,
		big_blind=2,
	)

	for street, player, action in actions:
		history.add_event(
			"action",
			street=street,
			player=player,
			action=action,
		)

	return history


def _service():
	return StatisticsService(
		MemoryPlayerRepository(),
		MemoryStatisticsRepository(),
		MemoryAgentMemoryRepository(),
	)


def test_fold_to_cbet_tracks_first_response_opportunity():
	collector = HandStatisticsAdapter().process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "call"),
				("preflop", "carol", "call"),
				("flop", "bob", "check"),
				("flop", "carol", "check"),
				("flop", "alice", "bet"),
				("flop", "bob", "fold"),
				("flop", "carol", "call"),
			]
		)
	)

	bob = collector.get_player("bob")
	carol = collector.get_player("carol")

	assert bob.fold_to_cbet_opportunities == 1
	assert bob.folds_to_cbet == 1
	assert bob.fold_to_cbet == 1.0

	assert carol.fold_to_cbet_opportunities == 1
	assert carol.folds_to_cbet == 0
	assert carol.fold_to_cbet == 0.0


def test_raise_to_cbet_ends_direct_fold_to_cbet_window():
	collector = HandStatisticsAdapter().process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "call"),
				("preflop", "carol", "call"),
				("flop", "bob", "check"),
				("flop", "carol", "check"),
				("flop", "alice", "bet"),
				("flop", "bob", "raise"),
				("flop", "carol", "fold"),
			]
		)
	)

	bob = collector.get_player("bob")
	carol = collector.get_player("carol")

	assert bob.fold_to_cbet_opportunities == 1
	assert bob.folds_to_cbet == 0
	assert carol.fold_to_cbet_opportunities == 0


def test_aggression_factor_is_split_by_street():
	collector = HandStatisticsAdapter().process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "call"),
				("preflop", "carol", "fold"),
				("flop", "bob", "check"),
				("flop", "alice", "bet"),
				("flop", "bob", "call"),
				("turn", "bob", "bet"),
				("turn", "alice", "call"),
				("river", "bob", "bet"),
				("river", "alice", "raise"),
				("river", "bob", "call"),
			]
		)
	)

	alice = collector.get_player("alice")
	bob = collector.get_player("bob")

	assert alice.flop_aggressive_actions == 1
	assert alice.flop_calls == 0
	assert alice.flop_aggression_factor == 1.0
	assert alice.turn_aggressive_actions == 0
	assert alice.turn_calls == 1
	assert alice.turn_aggression_factor == 0.0
	assert alice.river_aggressive_actions == 1
	assert alice.river_calls == 0
	assert alice.river_aggression_factor == 1.0

	assert bob.flop_calls == 1
	assert bob.turn_aggressive_actions == 1
	assert bob.river_aggressive_actions == 1
	assert bob.river_calls == 1


def test_street_counters_persist_and_merge_across_sessions():
	service = _service()

	first = HandStatisticsAdapter().process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "call"),
				("preflop", "carol", "fold"),
				("flop", "bob", "check"),
				("flop", "alice", "bet"),
				("flop", "bob", "fold"),
			]
		)
	)
	service.persist_collector(first)

	second = HandStatisticsAdapter().process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "call"),
				("preflop", "carol", "fold"),
				("flop", "bob", "check"),
				("flop", "alice", "bet"),
				("flop", "bob", "call"),
				("turn", "bob", "check"),
				("turn", "alice", "bet"),
				("turn", "bob", "call"),
			]
		)
	)
	service.persist_collector(second)

	bob_player = service.player_repository.get_by_name("bob")
	record = service.get_player_statistics(bob_player.id)

	assert record.fold_to_cbet_opportunities == 2
	assert record.folds_to_cbet == 1
	assert record.flop_calls == 1
	assert record.turn_calls == 1
