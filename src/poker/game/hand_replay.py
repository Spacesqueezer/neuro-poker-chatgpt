from dataclasses import dataclass

from poker.game.actions import PlayerAction
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.player.player import Player


@dataclass(frozen=True)
class ReplayVerification:
	mode: str
	hand_id: str | int
	ok: bool
	errors: tuple[str, ...]


class HandReplayVerifier:
	def verify(self, history):
		if history.seed is None:
			return self._verify_structural(history)
		return self._verify_exact(history)

	def _verify_exact(self, history):
		state = GameState()
		for player_data in history.players:
			state.add_player(Player(player_data["name"], player_data["starting_chips"]))

		dealer_index = next(
			index
			for index, player in enumerate(state.players)
			if player.name == history.dealer
		)
		state.dealer_button_index = (dealer_index - 1) % len(state.players)

		controller = HandController(
			Dealer(seed=history.seed),
			small_blind=history.small_blind,
			big_blind=history.big_blind,
		)
		controller.start_hand(state)

		errors = []
		actual_cards = {
			player.name: [str(card) for card in player.hand.cards]
			for player in state.players
		}
		expected_cards = {
			player["name"]: list(player.get("cards", []))
			for player in history.players
		}
		if actual_cards != expected_cards:
			errors.append(f"hole cards mismatch: expected={expected_cards} actual={actual_cards}")

		for event in history.events:
			if event.type != "action":
				continue

			current = controller.current_player(state)
			expected_player = event.data["player"]
			if current is None or current.name != expected_player:
				actual_name = current.name if current is not None else None
				errors.append(
					f"actor mismatch before action: expected={expected_player} actual={actual_name}"
				)
				break

			action = PlayerAction(event.data["action"])
			amount = event.data.get("requested_amount", 0)
			try:
				controller.process_action(state, action, amount)
			except Exception as error:
				errors.append(f"replay action failed for {expected_player}: {error}")
				break

		if not errors:
			expected = self._canonical(history)
			actual = self._canonical(controller.hand_history)
			if actual != expected:
				errors.append("replayed history does not exactly match the recorded history")

		return ReplayVerification(
			mode="exact",
			hand_id=history.hand_id,
			ok=not errors,
			errors=tuple(errors),
		)

	def _verify_structural(self, history):
		errors = []
		start_total = sum(player.get("starting_chips", 0) for player in history.players)
		if history.final_stacks:
			final_total = sum(history.final_stacks.values())
			if final_total != start_total:
				errors.append(f"chip conservation failed: start={start_total} final={final_total}")

		cards = []
		for player in history.players:
			cards.extend(player.get("cards", []))
		for event in history.events:
			if event.type == "street":
				cards.extend(event.data.get("board", []))
			elif event.type == "showdown":
				cards.extend(event.data.get("board", []))
		# Street events contain cumulative boards, so only duplicate hole cards are checked here.
		hole_cards = [card for player in history.players for card in player.get("cards", [])]
		if len(hole_cards) != len(set(hole_cards)):
			errors.append("duplicate hole cards in recorded history")

		if history.result is None:
			errors.append("history is incomplete")

		return ReplayVerification(
			mode="structural",
			hand_id=history.hand_id,
			ok=not errors,
			errors=tuple(errors),
		)

	def _canonical(self, history):
		payload = history.to_dict()
		payload.pop("hand_id", None)
		return payload
