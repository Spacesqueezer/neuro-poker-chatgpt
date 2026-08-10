#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poker.game.hand_history import HandHistoryStore


DEFAULT_HISTORY = PROJECT_ROOT / "artifacts" / "hand_history.jsonl"


def format_cards(cards):
	return " ".join(cards) or "-"


def get_showdown_event(history):
	for event in reversed(history.events):
		if event.type == "showdown":
			return event
	return None


def get_uncontested_event(history):
	for event in reversed(history.events):
		if event.type == "uncontested":
			return event
	return None


def result_label(history):
	showdown = get_showdown_event(history)
	if showdown is not None:
		winners = []
		for pot in showdown.data.get("pots", []):
			if pot.get("kind") != "refund":
				for winner in pot.get("winners", []):
					if winner not in winners:
						winners.append(winner)
		return "showdown:" + ",".join(winners) if winners else "showdown"

	uncontested = get_uncontested_event(history)
	if uncontested is not None:
		return f"uncontested:{uncontested.data['winner']}"

	return history.result or "incomplete"


def format_event(event):
	data = event.data
	if event.type == "blinds":
		return (
			f"BLINDS   {data['small_blind_player']} posts {data['small_blind']}; "
			f"{data['big_blind_player']} posts {data['big_blind']} "
			f"| pot={data.get('pot', '?')} target={data.get('target', '?')}"
		)
	if event.type == "action":
		amount = data.get("contributed", 0)
		requested = data.get("requested_amount", 0)
		requested_text = f" target={requested}" if data["action"] in {"bet", "raise"} and requested else ""
		return (
			f"{data['street'].upper():8} {data['player']:<10} {data['action']:<7}{requested_text:<11} "
			f"paid={amount:<3} chips={data.get('chips_before', '?')}->{data.get('chips_after', '?')} "
			f"bet={data.get('bet_before', '?')}->{data.get('bet_after', '?')} "
			f"contrib={data.get('total_contribution', '?')} pot={data.get('pot', '?')} "
			f"target={data.get('target', '?')}"
		)
	if event.type == "street":
		stacks = data.get("stacks", {})
		stack_text = " ".join(f"{name}={chips}" for name, chips in stacks.items())
		return (
			f"{data['street'].upper():8} board=[{format_cards(data['board'])}] "
			f"pot={data['pot']}" + (f" stacks=[{stack_text}]" if stack_text else "")
		)
	if event.type == "uncontested":
		return f"RESULT   {data['winner']} wins uncontested payout={data['payout']}"
	if event.type == "showdown":
		lines = [f"SHOWDOWN board=[{format_cards(data['board'])}]"]
		for player, result in data["results"].items():
			refund = result.get("refund", 0)
			refund_text = f" refund={refund}" if refund else ""
			lines.append(
				f"         {player:<10} {result['rank'].replace('_', ' ')} "
				f"[{format_cards(result['cards'])}] payout={result['payout']}{refund_text}"
			)
		pot_number = 0
		for pot in data.get("pots", []):
			if pot["kind"] == "refund":
				lines.append(f"         refund {pot['amount']}: {', '.join(pot['winners'])}")
				continue
			pot_number += 1
			label = "main" if pot_number == 1 else f"side {pot_number - 1}"
			lines.append(
				f"         {label} {pot['amount']}: eligible=[{', '.join(pot['eligible'])}] "
				f"winner=[{', '.join(pot['winners'])}]"
			)
		return "\n".join(lines)
	return f"{event.type}: {data}"


def total_starting_chips(history):
	return sum(player.get("starting_chips", 0) for player in history.players)


def total_final_chips(history):
	return sum(history.final_stacks.values()) if history.final_stacks else None


def print_summary(history, index):
	players = ", ".join(item["name"] for item in history.players)
	seed = history.seed if history.seed is not None else "scripted"
	print(
		f"[{index:>3}] id={history.hand_id} seed={str(seed):<10} dealer={history.dealer:<8} "
		f"players=[{players}] result={result_label(history)}"
	)


def print_history(history):
	print("=" * 88)
	print(f"Hand #{history.hand_id}")
	print(f"Seed: {history.seed if history.seed is not None else 'scripted'}")
	print(f"Dealer: {history.dealer} | Blinds: {history.small_blind}/{history.big_blind}")
	print("Players:")
	for player in history.players:
		final = history.final_stacks.get(player["name"], "?")
		start = player["starting_chips"]
		delta = final - start if isinstance(final, int) else None
		delta_text = f"{delta:+d}" if delta is not None else "?"
		print(
			f"  {player['name']:<10} start={start:<5} final={str(final):<5} delta={delta_text:<6} "
			f"hand=[{format_cards(player.get('cards', []))}]"
		)

	print("\nTimeline:")
	for number, event in enumerate(history.events, start=1):
		formatted = format_event(event)
		lines = formatted.splitlines()
		print(f"  {number:02d}. {lines[0]}")
		for line in lines[1:]:
			print(f"      {line}")

	start_total = total_starting_chips(history)
	final_total = total_final_chips(history)
	print("\nSummary:")
	print(f"  Result: {result_label(history)}")
	print(f"  Chip total: start={start_total} final={final_total if final_total is not None else '?'}")
	if final_total is not None:
		print(f"  Conservation: {'OK' if start_total == final_total else 'BROKEN'}")
	if history.seed is not None:
		print(f"  Replay seed: {history.seed}")
	print("=" * 88)


def print_stats(histories):
	complete = [history for history in histories if history.result is not None]
	showdowns = [history for history in complete if get_showdown_event(history) is not None]
	uncontested = [history for history in complete if get_uncontested_event(history) is not None]
	broken = []
	for history in complete:
		final_total = total_final_chips(history)
		if final_total is not None and final_total != total_starting_chips(history):
			broken.append(history.hand_id)
	print(f"Hands: {len(histories)}")
	print(f"Completed: {len(complete)}")
	print(f"Showdowns: {len(showdowns)}")
	print(f"Uncontested: {len(uncontested)}")
	print(f"Chip conservation failures: {len(broken)}")
	if broken:
		print(f"Broken hand ids: {', '.join(str(hand_id) for hand_id in broken)}")


def select_history(histories, hand):
	if hand is None:
		return len(histories), histories[-1]
	if hand < 1 or hand > len(histories):
		raise ValueError(f"History index {hand} is out of range 1..{len(histories)}")
	return hand, histories[hand - 1]


def browse(histories, start=None):
	index, history = select_history(histories, start)
	while True:
		print_history(history)
		try:
			command = input(f"history [{index}/{len(histories)}] > ").strip().lower()
		except (EOFError, KeyboardInterrupt):
			print()
			return
		if command in {"q", "quit", "exit"}:
			return
		if command in {"", "n", "next"}:
			index = min(index + 1, len(histories))
		elif command in {"p", "prev", "previous"}:
			index = max(index - 1, 1)
		elif command in {"l", "list"}:
			for list_index, item in enumerate(histories, start=1):
				print_summary(item, list_index)
			continue
		elif command.startswith("g ") or command.startswith("goto "):
			try:
				index = int(command.split()[-1])
			except ValueError:
				print("Use: goto N")
				continue
			if index < 1 or index > len(histories):
				print(f"Index must be 1..{len(histories)}")
				continue
		else:
			print("Commands: Enter/n=next, p=previous, goto N, list, q")
			continue
		history = histories[index - 1]


def main():
	parser = argparse.ArgumentParser(description="View recorded poker hand histories")
	parser.add_argument("command", choices=["list", "show", "browse", "stats"], nargs="?", default="browse")
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
	if args.command == "stats":
		print_stats(histories)
		return
	if args.command == "browse":
		browse(histories, args.hand)
		return

	_, history = select_history(histories, args.hand)
	print_history(history)


if __name__ == "__main__":
	main()
