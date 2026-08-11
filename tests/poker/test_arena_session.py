from types import SimpleNamespace

import poker.arena.session as session_module
from poker.arena.session import ArenaSession


def test_arena_session_passes_current_stacks_to_next_hand(monkeypatch):
	calls = []
	results = [
		SimpleNamespace(final_stacks={"alice": 110, "bob": 90}),
		SimpleNamespace(final_stacks={"alice": 95, "bob": 105}),
	]

	def fake_play_hand(agents, seed, dealer_name, starting_stacks):
		calls.append({
			"seed": seed,
			"dealer_name": dealer_name,
			"starting_stacks": dict(starting_stacks),
		})
		return results[len(calls) - 1]

	monkeypatch.setattr(session_module, "play_hand", fake_play_hand)

	session = ArenaSession.create(["alice", "bob"], 100)
	agents = {"alice": object(), "bob": object()}

	session.play_next_hand(agents, seed=42, dealer_name="alice")
	session.play_next_hand(agents, seed=43, dealer_name="bob")

	assert calls[0]["starting_stacks"] == {"alice": 100, "bob": 100}
	assert calls[1]["starting_stacks"] == {"alice": 110, "bob": 90}
	assert session.current_stacks() == {"alice": 95, "bob": 105}
	assert session.completed_hands == 2


def test_arena_session_rejects_chip_conservation_failure():
	session = ArenaSession.create(["alice", "bob"], 100)
	history = SimpleNamespace(final_stacks={"alice": 120, "bob": 90})

	try:
		session.apply_hand_result(history)
	except ValueError as error:
		assert "Chip conservation failed" in str(error)
	else:
		raise AssertionError("Expected chip conservation failure")


def test_arena_session_stops_after_player_bust(monkeypatch):
	calls = []

	def fake_play_hand(agents, seed, dealer_name, starting_stacks):
		calls.append(seed)
		return SimpleNamespace(final_stacks={"alice": 200, "bob": 0})

	monkeypatch.setattr(session_module, "play_hand", fake_play_hand)

	class Stats:
		failed_hands = 0

		def record_result(self, seed, result):
			pass

	session = ArenaSession.create(["alice", "bob"], 100)
	session.run({"alice": object(), "bob": object()}, hands=10, seed=42, stats=Stats())

	assert calls == [42]
	assert session.completed_hands == 1
	assert session.is_finished()
