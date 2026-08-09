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


ACTION_COMMANDS = {
	"fold": PlayerAction.FOLD,
	"check": PlayerAction.CHECK,
	"call": PlayerAction.CALL,
	"bet": PlayerAction.BET,
	"raise": PlayerAction.RAISE,
	"all-in": PlayerAction.ALL_IN,
	"allin": PlayerAction.ALL_IN,
}

AMOUNT_COMMANDS = {"bet", "raise"}


def format_cards(cards):
	return " ".join(str(card) for card in cards) or "-"


def print_help():
	print("Commands:")
	print("  check | call | fold | all-in")
	print("  bet N | raise N")
	print("  state | players | deal | help | quit")


def print_showdown(controller):
	if not controller.showdown_results:
		return

	print("Showdown:")
	for player, result in controller.showdown_results.items():
		marker = "WIN" if player in controller.showdown_winners else "   "
		payout = controller.showdown_payouts.get(player, 0)
		print(
			f"  {marker} {player.name}: {result.rank.name.lower().replace('_', ' ')} "
			f"[{format_cards(result.cards)}] payout={payout}"
		)
	print()


def prepare_next_hand(state):
	if len(state.players) < 2:
		raise ValueError("At least two players are required")

	old_players = list(state.players)
	old_dealer_index = state.dealer_button_index
	survivors = [player for player in old_players if player.chips > 0]

	if len(survivors) < 2:
		raise ValueError("Not enough players with chips for another hand")

	if len(survivors) == len(old_players):
		return

	if old_dealer_index is None:
		state.players[:] = survivors
		state.dealer_button_index = None
		state.turn_order.players = state.players
		return

	next_dealer = None
	for offset in range(1, len(old_players) + 1):
		candidate = old_players[(old_dealer_index + offset) % len(old_players)]
		if candidate.chips > 0:
			next_dealer = candidate
			break

	state.players[:] = survivors
	state.turn_order.players = state.players
	next_index = state.players.index(next_dealer)
	state.dealer_button_index = (next_index - 1) % len(state.players)


def print_state(state, controller):
	print()
	print(f"Street: {state.round_manager.street.value}")
	print(f"Board:  {format_cards(state.board.cards)}")
	committed = sum(player.current_bet for player in state.players)
	total_pot = controller.total_pot(state)
	if committed:
		print(f"Pot:    {total_pot} ({state.betting.pot} collected + {committed} committed)")
	else:
		print(f"Pot:    {total_pot}")
	print(f"Target: {state.betting.current_bet}")

	if state.dealer_button_index is not None:
		dealer = state.players[state.dealer_button_index]
		small_blind = state.players[controller.small_blind_index]
		big_blind = state.players[controller.big_blind_index]
		print(f"Dealer: {dealer.name}")
		print(f"Blinds: {small_blind.name} {controller.small_blind} / {big_blind.name} {controller.big_blind}")

	print()
	print_players(state, controller)
	if state.round_manager.street == GameStreet.SHOWDOWN:
		print_showdown(controller)


def print_players(state, controller):
	current_player = controller.current_player(state)
	for index, player in enumerate(state.players):
		terminal_streets = {GameStreet.SHOWDOWN, GameStreet.COMPLETE}
		marker = ">" if player is current_player and state.round_manager.street not in terminal_streets else " "
		status = "folded" if player.folded else "active"
		position = controller.position_name(state, index)
		position_text = f" {position}" if position else ""
		print(
			f"{marker} {player.name}{position_text}: chips={player.chips} "
			f"bet={player.current_bet} status={status} "
			f"hand=[{format_cards(player.hand.cards)}]"
		)
	print()


def parse_action(command):
	parts = command.strip().lower().split()
	if not parts:
		return None, 0

	name = parts[0]
	if name not in ACTION_COMMANDS:
		raise ValueError("Unknown command. Type 'help' for available commands")

	if name in AMOUNT_COMMANDS:
		if len(parts) != 2:
			raise ValueError(f"Usage: {name} N")
		try:
			amount = int(parts[1])
		except ValueError as error:
			raise ValueError(f"Usage: {name} N, where N is a positive integer") from error
		if amount <= 0:
			raise ValueError(f"{name.capitalize()} amount must be positive")
		return ACTION_COMMANDS[name], amount

	if len(parts) != 1:
		raise ValueError(f"Usage: {name}")

	return ACTION_COMMANDS[name], 0


def main():
	random.seed(42)

	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 100))
	state.add_player(Player("Carol", 100))

	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	print("Manual Texas Hold'em hand")
	print_help()
	print_state(state, controller)

	while True:
		try:
			command = input("action> ").strip()
		except (EOFError, KeyboardInterrupt):
			print()
			break

		name = command.lower()
		if name in {"quit", "exit"}:
			break
		if name == "help":
			print_help()
			continue
		if name == "state":
			print_state(state, controller)
			continue
		if name == "players":
			print_players(state, controller)
			continue
		if name == "deal":
			try:
				prepare_next_hand(state)
				controller.start_hand(state)
				print_state(state, controller)
			except ValueError as error:
				print(f"Error: {error}")
			continue
		if state.round_manager.street in {GameStreet.SHOWDOWN, GameStreet.COMPLETE}:
			status = "showdown" if state.round_manager.street == GameStreet.SHOWDOWN else "complete"
			print(f"Hand is {status}. Type 'deal' for the next hand or 'quit'.")
			continue

		try:
			action, amount = parse_action(command)
			if action is None:
				continue
			controller.process_action(state, action, amount)
			print_state(state, controller)
		except (ValueError, RuntimeError) as error:
			print(f"Error: {error}")


if __name__ == "__main__":
	main()
