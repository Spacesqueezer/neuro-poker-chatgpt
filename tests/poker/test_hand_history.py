from poker.game.hand_history import HandHistory, HandHistoryStore


def test_hand_history_round_trips_through_jsonl(tmp_path):
	history = HandHistory(
		hand_id=7,
		players=[{"name": "Alice", "starting_chips": 100, "cards": ["A♠", "K♠"]}],
		dealer="Alice",
		small_blind=1,
		big_blind=2,
		seed=12345,
	)
	history.add_event("action", street="preflop", player="Alice", action="raise", contributed=6)
	history.finish("showdown", [])

	store = HandHistoryStore(tmp_path / "history.jsonl")
	store.append(history)
	loaded = store.load_all()

	assert len(loaded) == 1
	assert loaded[0].hand_id == 7
	assert loaded[0].events[0].data["action"] == "raise"
	assert loaded[0].result == "showdown"
	assert loaded[0].seed == 12345


def test_hand_history_finish_captures_final_stacks():
	class PlayerStub:
		def __init__(self, name, chips):
			self.name = name
			self.chips = chips

	history = HandHistory(1, [], "Alice", 1, 2)
	history.finish("complete", [PlayerStub("Alice", 120), PlayerStub("Bob", 80)])

	assert history.final_stacks == {"Alice": 120, "Bob": 80}


def test_hand_history_loads_old_records_without_seed(tmp_path):
	path = tmp_path / "history.jsonl"
	path.write_text(
		'{"hand_id": 1, "players": [], "dealer": "Alice", "small_blind": 1, "big_blind": 2, "events": [], "final_stacks": {}, "result": null}\n',
		encoding="utf-8",
	)

	loaded = HandHistoryStore(path).load_all()

	assert loaded[0].seed is None
