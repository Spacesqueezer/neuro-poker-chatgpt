#!/usr/bin/env python3

import argparse
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poker.api import ActionDecision, play_hand
from poker.game.actions import PlayerAction


class RandomSmokeAgent:
	def __init__(self, rng):
		self.rng = rng

	def choose_action(self, state, legal):
		choices = []
		for action in legal.actions:
			if action == PlayerAction.BET:
				choices.append(ActionDecision(action, legal.min_bet))
			elif action == PlayerAction.RAISE:
				choices.append(ActionDecision(action, legal.min_raise_to))
			else:
				choices.append(ActionDecision(action))
		return self.rng.choice(choices)


def assert_invariants(history, starting_total):
	if sum(history.final_stacks.values()) != starting_total:
		raise AssertionError("chip conservation failed")
	if any(chips < 0 for chips in history.final_stacks.values()):
		raise AssertionError("negative player stack")
	if history.result is None:
		raise AssertionError("terminal hand has no completed HandHistory")

	board = []
	for event in history.events:
		if event.type in {"street", "showdown"}:
			board = list(event.data.get("board", board))
	cards = [
		card
		for player in history.players
		for card in player.get("cards", [])
	] + board
	if len(cards) != len(set(cards)):
		raise AssertionError("duplicate visible cards")


def run_hand(seed, rng, player_count=3, stack=100):
	agent = RandomSmokeAgent(rng)
	agents = {f"P{index + 1}": agent for index in range(player_count)}
	history = play_hand(
		agents,
		seed=seed,
		starting_stack=stack,
	)
	assert_invariants(history, player_count * stack)
	return history


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
	print("Crashes: 0")


if __name__ == "__main__":
	main()
