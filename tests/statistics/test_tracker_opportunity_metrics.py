from poker.game.hand_history import HandHistory
from poker.statistics.hand_adapter import HandStatisticsAdapter
from poker.statistics.hand_mapping import HandStatisticsMapper


def _history(actions):
	history = HandHistory(
		hand_id="tracker-opportunities",
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


def test_three_bet_and_fold_to_three_bet_are_opportunity_aware():
	history = _history(
		[
			("preflop", "alice", "raise"),
			("preflop", "bob", "fold"),
			("preflop", "carol", "raise"),
			("preflop", "alice", "fold"),
		]
	)

	mapped = HandStatisticsMapper().map_hand(history)
	players = {player["name"]: player for player in mapped["players"]}

	assert players["bob"]["three_bet_opportunity"] is True
	assert players["bob"]["three_bet"] is False

	assert players["carol"]["three_bet_opportunity"] is True
	assert players["carol"]["three_bet"] is True

	assert players["alice"]["fold_to_three_bet_opportunity"] is True
	assert players["alice"]["folded_to_three_bet"] is True


def test_cbet_and_aggression_inputs_are_derived_from_postflop_actions():
	history = _history(
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

	collector = HandStatisticsAdapter().process_hand(history)

	alice = collector.get_player("alice")
	bob = collector.get_player("bob")

	assert alice.cbet_opportunities == 1
	assert alice.cbets == 1
	assert alice.cbet == 1.0
	assert alice.aggressive_actions == 2
	assert alice.calls == 0
	assert alice.aggression_factor == 2.0

	assert bob.aggressive_actions == 0
	assert bob.calls == 2
	assert bob.aggression_factor == 0.0


def test_donk_bet_removes_cbet_opportunity():
	history = _history(
		[
			("preflop", "alice", "raise"),
			("preflop", "bob", "call"),
			("preflop", "carol", "fold"),
			("flop", "bob", "bet"),
			("flop", "alice", "call"),
		]
	)

	collector = HandStatisticsAdapter().process_hand(history)
	alice = collector.get_player("alice")

	assert alice.cbet_opportunities == 0
	assert alice.cbets == 0


def test_tracker_rates_accumulate_across_hands():
	adapter = HandStatisticsAdapter()

	adapter.process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "raise"),
				("preflop", "alice", "fold"),
				("preflop", "carol", "fold"),
			]
		)
	)
	adapter.process_hand(
		_history(
			[
				("preflop", "alice", "raise"),
				("preflop", "bob", "fold"),
				("preflop", "carol", "call"),
			]
		)
	)

	alice = adapter.collector.get_player("alice")
	bob = adapter.collector.get_player("bob")

	assert alice.fold_to_three_bet_opportunities == 1
	assert alice.folds_to_three_bet == 1
	assert alice.fold_to_three_bet == 1.0

	assert bob.three_bet_opportunities == 2
	assert bob.three_bets == 1
	assert bob.three_bet == 0.5
