#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poker.game.hand_history import HandHistoryStore


DEFAULT_HISTORY = PROJECT_ROOT / "artifacts" / "hand_history.jsonl"


def format_event(event):
	data = event.data
	if event.type == "blinds":
		return (
			f"BLINDS {data['small_blind_player']} {data['small_blind']} / "
			f"{data['big_blind_player']} {data['big_blind']}"
		)
	if event.type == "action":
		amount = data.get("contributed", 0)
		suffix = f" +{amount}" if amount else ""
		return f"{data['street'].upper():8} {data['player']}: {data['action']}{suffix}"
	if event.type == "street":
		return f"{data['street'].upper():8} board=[{' '.join(data['board'])}] pot={data['pot']}"
	if event.type == "uncontested":
		return f"RESULT   {data['winner']} wins uncontested payout={data['payout']}"
	if event.type == "showdown":
		lines = [f"SHOWDOWN board=[{' '.join(data['board'])}]"]
		for player, result in data["results"].items():
			refund = result.get("refund", 0)
			refund_text = f" refund={refund}" if refund else ""
			lines.append(
				f"         {player}: {result['rank'].replace('_', ' ')} "
				f"[{' '.join(result['cards'])}] payout={result['payout']}{refund_text}"
			)
		for index, pot in enumerate(data.get("pots", []), start=1):
			if pot["kind"] == "refund":
				lines.append(f"         refund {pot['amount']}: {', '.join(pot['winners'])}")
			else:
				label = "main" if index == 1 else f"side {index - 1}"
				lines.append(
					f"         {label} {pot['amount']}: eligible=[{', '.join(pot['eligible'])}] "
					f"winner=[{', '.join(pot['winners'])}]"
				)
		return "\n".join(lines)
	return f"{event.type}: {data}"


def print_summary(history, index):
	players = ", ".join(item["name"] for item in history.players)
	result = history.result or "incomplete"
	print(f"[{index}] id={history.hand_id} dealer={history.dealer:<8} players=[{players}] result={result}")


def print_history(history):
	print(f"Hand #{history.hand_id}")
	print(f"Dealer: {history.dealer}")
	print(f"Blinds: {history.small_blind}/{history.big_blind}")
	print("Players:")
	for player in history.players:
		print(
			f"  {player['name']}: start={player['starting_chips']} "
			f"hand=[{' '.join(player.get('cards', []))}]"
		)
	print()
	for event in history.events:
		print(format_event(event))
	if history.final_stacks:
		print("\nFinal stacks:")
		for name, chips in history.final_stacks.items():
			print(f"  {name}: {chips}")


def main():
	parser = argparse.ArgumentParser(description="View recorded poker hand histories")
	parser.add_argument("command", choices=["list", "show"])
	parser.add_argument("hand", nargs="?", type=int, help="1-based history index; default is latest")
	parser.add_argument("--file", default=str(DEFAULT_HISTORY))
	args = parser.parse_args()

	histories = HandHistoryStore(args.file).load_all()
	if not histories:
		print(f"No hand histories found in {args.file}")
		return

	if args.command == "list":
		for index, history in enumerate(histories, start=1):
			print_summary(history, index)
		return

	if args.hand is None:
		history = histories[-1]
	else:
		if args.hand < 1 or args.hand > len(histories):
			raise SystemExit(f"History index {args.hand} is out of range 1..{len(histories)}")
		history = histories[args.hand - 1]
	print_history(history)


if __name__ == "__main__":
	main()
