from poker.game.hand_history import HandHistory
from poker.statistics.hand_adapter import HandStatisticsAdapter
from poker.statistics.hand_mapping import HandStatisticsMapper


def _history():
	history = HandHistory(
		hand_id="stats-bridge",
		players=[
			{"name": "alice", "starting_chips": 100},
			{"name": "bob", "starting_chips": 100},
			{"name": "carol", "starting_chips": 100},
		],
		dealer="alice",
		small_blind=1,
		big_blind=2,
	)

	history.add_event("action", street="preflop", player="alice", action="raise")
	history.add_event("action", street="preflop", player="bob", action="fold")
	history.add_event("action", street="preflop", player="carol", action="raise")
	history.add_event("action", street="preflop", player="alice", action="call")
	history.add_event(
		"showdown",
		results={
			"alice": {"payout": 0, "refund": 0},
			"carol": {"payout": 30, "refund": 0},
		},
	)

	return history


def test_mapper_preserves_existing_statistics_contract():
	mapped = HandStatisticsMapper().map_hand(
		{
			"players": [
				{
					"name": "legacy",
					"entered_pot": True,
					"raised_preflop": True,
					"three_bet": True,
					"showdown": True,
					"won_showdown": True,
				}
			]
		}
	)

	player = mapped["players"][0]

	assert player["entered_pot"] is True
	assert player["raised_preflop"] is True
	assert player["three_bet"] is True
	assert player["showdown"] is True
	assert player["won_showdown"] is True


def test_mapper_derives_statistics_from_real_hand_history_events():
	mapped = HandStatisticsMapper().map_hand(_history())
	players = {
		player["name"]: player
		for player in mapped["players"]
	}

	assert players["alice"]["entered_pot"] is True
	assert players["alice"]["raised_preflop"] is True
	assert players["alice"]["three_bet"] is False
	assert players["alice"]["showdown"] is True
	assert players["alice"]["won_showdown"] is False

	assert players["bob"]["entered_pot"] is False
	assert players["bob"]["raised_preflop"] is False
	assert players["bob"]["showdown"] is False

	assert players["carol"]["entered_pot"] is True
	assert players["carol"]["raised_preflop"] is True
	assert players["carol"]["three_bet"] is True
	assert players["carol"]["showdown"] is True
	assert players["carol"]["won_showdown"] is True


def test_adapter_updates_collector_from_hand_history():
	collector = HandStatisticsAdapter().process_hand(_history())

	alice = collector.get_player("alice")
	bob = collector.get_player("bob")
	carol = collector.get_player("carol")

	assert alice.hands == 1
	assert alice.vpip == 1.0
	assert alice.pfr == 1.0
	assert alice.three_bets == 0
	assert alice.wtsd == 1.0
	assert alice.wsd == 0.0

	assert bob.hands == 1
	assert bob.vpip == 0.0
	assert bob.pfr == 0.0
	assert bob.wtsd == 0.0

	assert carol.hands == 1
	assert carol.vpip == 1.0
	assert carol.pfr == 1.0
	assert carol.three_bets == 1
	assert carol.wtsd == 1.0
	assert carol.wsd == 1.0
