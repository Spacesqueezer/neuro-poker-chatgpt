from poker.game.actions import PlayerAction
from poker.game.hand_history import HandHistory
from poker.game.hand_replay import HandReplayVerifier
from tools.manual_scenarios import create_scenario


def test_seeded_history_replays_exactly():
	state, controller, _ = create_scenario("default", seed=12345)
	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.FOLD)

	result = HandReplayVerifier().verify(controller.hand_history)

	assert result.mode == "exact"
	assert result.ok
	assert result.errors == ()


def test_seeded_history_without_position_metadata_replays_exactly():
	state, controller, _ = create_scenario("default", seed=12345)
	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.FOLD)

	payload = controller.hand_history.to_dict()
	for player in payload["players"]:
		player.pop("position", None)

	legacy_history = HandHistory.from_dict(payload)
	result = HandReplayVerifier().verify(legacy_history)

	assert result.mode == "exact"
	assert result.ok
	assert result.errors == ()


def test_seeded_history_with_position_metadata_still_replays_exactly():
	state, controller, _ = create_scenario("default", seed=54321)
	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.FOLD)

	assert all(
		"position" in player
		for player in controller.hand_history.players
	)

	result = HandReplayVerifier().verify(controller.hand_history)

	assert result.mode == "exact"
	assert result.ok


def test_scripted_history_uses_structural_verification():
	history = HandHistory(
		hand_id="scripted",
		players=[
			{"name": "Alice", "starting_chips": 100, "cards": ["A♠", "A♥"]},
			{"name": "Bob", "starting_chips": 100, "cards": ["K♠", "K♥"]},
		],
		dealer="Alice",
		small_blind=1,
		big_blind=2,
	)
	class PlayerStub:
		def __init__(self, name, chips):
			self.name = name
			self.chips = chips

	history.finish("complete", [PlayerStub("Alice", 102), PlayerStub("Bob", 98)])

	result = HandReplayVerifier().verify(history)

	assert result.mode == "structural"
	assert result.ok


def test_structural_verification_detects_broken_chip_conservation():
	history = HandHistory(
		hand_id="broken",
		players=[
			{"name": "Alice", "starting_chips": 100, "cards": ["A♠", "A♥"]},
			{"name": "Bob", "starting_chips": 100, "cards": ["K♠", "K♥"]},
		],
		dealer="Alice",
		small_blind=1,
		big_blind=2,
	)
	history.final_stacks = {"Alice": 150, "Bob": 60}
	history.result = "complete"

	result = HandReplayVerifier().verify(history)

	assert not result.ok
	assert "chip conservation failed" in result.errors[0]
