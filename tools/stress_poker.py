#!/usr/bin/env python3

import argparse
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


TERMINAL_STREETS = {GameStreet.SHOWDOWN, GameStreet.COMPLETE}


def create_hand(seed, player_count=3, stack=100):
	state = GameState()
	for index in range(player_count):
		state.add_player(Player(f"P{index + 1}", stack))
	controller = HandController(Dealer(seed=seed))
	controller.start_hand(state)
	return state, controller


def legal_actions(state, controller):
	player = controller.current_player(state)
	if player is None or player.chips <= 0:
		return []

	target = state.betting.current_bet
	facing = target - player.current_bet
	actions = []

	if facing > 0:
		actions.append((PlayerAction.FOLD, 0))
		actions.append((PlayerAction.CALL, 0))
	else:
		actions.append((PlayerAction.CHECK, 0))

	max_target = player.current_bet + player.chips
	if target == 0 and player.chips >= controller.big_blind:
		actions.append((PlayerAction.BET, controller.big_blind))

	if target > 0 and controller.betting_round.can_raise(player):
		minimum_target = target + controller.minimum_raise
		if max_target >= minimum_target:
			actions.append((PlayerAction.RAISE, minimum_target))

	if player.chips > 0:
		actions.append((PlayerAction.ALL_IN, 0))

	return actions


def assert_invariants(state, controller, starting_total):
	if sum(player.chips for player in state.players) != starting_total:
		raise AssertionError("chip conservation failed")
	if any(player.chips < 0 for player in state.players):
		raise AssertionError("negative player stack")
	if state.betting.pot != 0:
		raise AssertionError("terminal hand left chips in collected pot")
	if controller.hand_history is None or controller.hand_history.result is None:
		raise AssertionError("terminal hand has no completed HandHistory")

	cards = [
		str(card)
		for player in state.players
		for card in player.hand.cards
	] + [str(card) for card in state.board.cards]
	if len(cards) != len(set(cards)):
		raise AssertionError("duplicate visible cards")


def run_hand(seed, rng, player_count=3, stack=100, max_actions=200):
	state, controller = create_hand(seed, player_count=player_count, stack=stack)
	starting_total = player_count * stack
	actions_taken = 0

	while state.round_manager.street not in TERMINAL_STREETS:
		choices = legal_actions(state, controller)
		if not choices:
			raise AssertionError("no legal action available in non-terminal state")
		action, amount = rng.choice(choices)
		controller.process_action(state, action, amount)
		actions_taken += 1
		if actions_taken > max_actions:
			raise AssertionError("hand exceeded action limit")

	assert_invariants(state, controller, starting_total)
	return controller.hand_history


def main():
	parser = argparse.ArgumentParser(description="Randomized poker engine smoke/stress runner")
	parser.add_argument("--hands", type=int, default=1000)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--players", type=int, default=3)
	parser.add_argument("--stack", type=int, default=100)
	args = parser.parse_args()

	if args.hands <= 0:
		raise SystemExit("--hands must be positive")
	if args.players < 2:
		raise SystemExit("--players must be at least 2")
	if args.stack < 2:
		raise SystemExit("--stack must be at least 2 with default blinds 1/2")

	rng = random.Random(args.seed)
	showdowns = 0
	uncontested = 0

	for index in range(args.hands):
		hand_seed = args.seed + index
		try:
			history = run_hand(
				hand_seed,
				rng,
				player_count=args.players,
				stack=args.stack,
			)
		except Exception as error:
			print(f"FAIL hand={index + 1} seed={hand_seed}: {error}")
			raise SystemExit(1) from error

		if history.result == "showdown":
			showdowns += 1
		else:
			uncontested += 1

	print(f"Hands: {args.hands}")
	print(f"Completed: {args.hands}")
	print(f"Showdowns: {showdowns}")
	print(f"Uncontested: {uncontested}")
	print("Chip conservation: OK")
	print("Duplicate visible cards: 0")
	print("Crashes: 0")


if __name__ == "__main__":
	main()
