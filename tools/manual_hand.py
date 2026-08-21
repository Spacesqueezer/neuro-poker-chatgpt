import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poker.game.actions import PlayerAction
from poker.game.hand_history import HandHistoryStore
from poker.game.round_manager import GameStreet
from tools.manual_scenarios import create_scenario, get_scenario, scenario_names

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
HISTORY_FILE = PROJECT_ROOT / "artifacts" / "hand_history.jsonl"


def format_cards(cards):
	return " ".join(str(card) for card in cards) or "-"


def print_help():
	print("Commands:")
	print("  check | call | fold | all-in")
	print("  bet N | raise N")
	print("  state | players | table | sitout NAME | sitin NAME | deal | scenario list | scenario NAME | help | quit")


def print_showdown(controller):
	if not controller.showdown_results:
		return

	print("Showdown:")
	for player, result in controller.showdown_results.items():
		marker = "WIN" if player in controller.showdown_winners else "   "
		payout = controller.showdown_payouts.get(player, 0)
		refund = controller.showdown_refunds.get(player, 0)
		refund_text = f" refund={refund}" if refund else ""
		print(
			f"  {marker} {player.name}: {result.rank.name.lower().replace('_', ' ')} "
			f"[{format_cards(result.cards)}] payout={payout}{refund_text}"
		)

	if controller.showdown_pots:
		print("Pots:")
		pot_index = 0
		for kind, amount, eligible, winners in controller.showdown_pots:
			if kind == "refund":
				print(f"  refund {amount}: {winners[0].name}")
				continue
			pot_index += 1
			label = "main" if pot_index == 1 else f"side {pot_index - 1}"
			eligible_names = ", ".join(player.name for player in eligible)
			winner_names = ", ".join(player.name for player in winners)
			print(f"  {label} {amount}: eligible=[{eligible_names}] winner=[{winner_names}]")
	print()



def print_table(state):
	print("Table:")
	button_seat = state.table.dealer_button_seat_index
	for seat in state.table.seats:
		marker = "BTN" if seat.index == button_seat else ""
		print(
			f"  seat={seat.index:<2} {seat.player.name:<10} chips={seat.player.chips:<5} "
			f"status={seat.status.value:<11} {marker}"
		)
	print()

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
			f"bet={player.current_bet} contrib={player.total_contribution} status={status} "
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


def find_seated_player(state, name):
	for seat in state.table.seats:
		if seat.player.name.lower() == name.strip().lower():
			return seat.player
	raise ValueError(f"Unknown seated player: {name}")


def print_scenarios():
	print("Scenarios:")
	for scenario_name in scenario_names():
		scenario = get_scenario(scenario_name)
		print(f"  {scenario.name:<12} {scenario.description}")
	print()


def print_scenario_banner(scenario, controller):
	print(f"Scenario: {scenario.name} - {scenario.description}")
	print(f"Hint: {scenario.hint}")
	seed = getattr(controller.dealer, "current_seed", None)
	if seed is not None:
		print(f"Seed: {seed}")


def save_completed_history(controller, saved_histories):
	if controller.hand_history is None or controller.hand_history.result is None:
		return
	history_key = id(controller.hand_history)
	if history_key in saved_histories:
		return
	HandHistoryStore(HISTORY_FILE).append(controller.hand_history)
	saved_histories.add(history_key)


def main():
	parser = argparse.ArgumentParser(description="Manual Texas Hold'em debug runner")
	parser.add_argument("--scenario", default="default", choices=scenario_names())
	parser.add_argument("--seed", type=int, help="Deterministic seed for default random hands")
	args = parser.parse_args()

	state, controller, scenario = create_scenario(args.scenario, seed=args.seed)
	saved_histories = set()

	print("Manual Texas Hold'em hand")
	print_help()
	print_scenario_banner(scenario, controller)
	print_state(state, controller)

	while True:
		try:
			command = input("action> ").strip()
		except (EOFError, KeyboardInterrupt):
			print()
			save_completed_history(controller, saved_histories)
			break

		name = command.lower()
		if name in {"quit", "exit"}:
			save_completed_history(controller, saved_histories)
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
		if name == "table":
			print_table(state)
			continue
		if name.startswith("sitout "):
			try:
				state.sit_out(find_seated_player(state, command.split(maxsplit=1)[1]))
				print_table(state)
			except ValueError as error:
				print(f"Error: {error}")
			continue
		if name.startswith("sitin "):
			try:
				state.sit_in(find_seated_player(state, command.split(maxsplit=1)[1]))
				print_table(state)
			except ValueError as error:
				print(f"Error: {error}")
			continue
		if name == "scenario list":
			print_scenarios()
			continue
		if name.startswith("scenario "):
			scenario_name = name.removeprefix("scenario ").strip()
			try:
				save_completed_history(controller, saved_histories)
				state, controller, scenario = create_scenario(scenario_name, seed=args.seed)
				print_scenario_banner(scenario, controller)
				print_state(state, controller)
			except ValueError as error:
				print(f"Error: {error}")
			continue
		if name == "deal":
			try:
				save_completed_history(controller, saved_histories)
				controller.start_hand(state)
				seed = getattr(controller.dealer, "current_seed", None)
				if seed is not None:
					print(f"Seed: {seed}")
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
