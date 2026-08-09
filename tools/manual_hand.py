#!/usr/bin/env python3

import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poker.game.actions import PlayerAction
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.game.round_manager import GameStreet
from poker.player.player import Player


def format_cards(cards):
	return " ".join(str(card) for card in cards) or "-"


def print_state(state, controller):
	print()
	print(f"Street: {state.round_manager.street.value}")
	print(f"Board:  {format_cards(state.board.cards)}")
	print(f"Pot:    {state.betting.pot}")
	print(f"Target: {state.betting.current_bet}")
	print()

	current_player = controller.current_player(state)
	for player in state.players:
		marker = ">" if player is current_player and state.round_manager.street != GameStreet.SHOWDOWN else " "
		status = "folded" if player.folded else "active"
		print(
			f"{marker} {player.name}: chips={player.chips} "
			f"bet={player.current_bet} status={status} "
			f"hand=[{format_cards(player.hand.cards)}]"
		)

	print()


def parse_action(command):
	parts = command.strip().lower().split()
	if not parts:
		return None, 0

	name = parts[0]
	amount = int(parts[1]) if len(parts) > 1 else 0

	actions = {
		"fold": PlayerAction.FOLD,
		"check": PlayerAction.CHECK,
		"call": PlayerAction.CALL,
		"bet": PlayerAction.BET,
		"raise": PlayerAction.RAISE,
		"all-in": PlayerAction.ALL_IN,
		"allin": PlayerAction.ALL_IN,
	}

	if name not in actions:
		raise ValueError("Unknown command")

	return actions[name], amount


def main():
	random.seed(42)

	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 100))
	state.add_player(Player("Carol", 100))

	controller = HandController(Dealer())
	controller.start_hand(state)

	print("Manual Texas Hold'em hand")
	print("Commands: check, call, bet N, raise N, fold, all-in, state, quit")
	print_state(state, controller)

	while state.round_manager.street != GameStreet.SHOWDOWN:
		try:
			command = input("action> ").strip()
		except (EOFError, KeyboardInterrupt):
			print()
			break

		if command.lower() in {"quit", "exit"}:
			break
		if command.lower() == "state":
			print_state(state, controller)
			continue

		try:
			action, amount = parse_action(command)
			if action is None:
				continue
			controller.process_action(state, action, amount)
			print_state(state, controller)
		except (ValueError, RuntimeError) as error:
			print(f"Error: {error}")

	if state.round_manager.street == GameStreet.SHOWDOWN:
		print("Hand reached showdown. Winner resolution is not implemented yet.")


if __name__ == "__main__":
	main()
