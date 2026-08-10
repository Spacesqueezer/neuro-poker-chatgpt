#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poker.game.hand_history import HandHistoryStore
from poker.game.hand_replay import HandReplayVerifier


DEFAULT_HISTORY = PROJECT_ROOT / "artifacts" / "hand_history.jsonl"


def main():
	parser = argparse.ArgumentParser(description="Verify recorded poker hand histories")
	parser.add_argument("--file", default=str(DEFAULT_HISTORY))
	parser.add_argument("--hand", type=int, help="Verify one 1-based history index")
	args = parser.parse_args()

	histories = HandHistoryStore(args.file).load_all()
	if not histories:
		print(f"No hand histories found in {args.file}")
		return

	if args.hand is not None:
		if args.hand < 1 or args.hand > len(histories):
			raise SystemExit(f"History index must be 1..{len(histories)}")
		histories = [histories[args.hand - 1]]

	verifier = HandReplayVerifier()
	results = [verifier.verify(history) for history in histories]

	exact = sum(result.mode == "exact" for result in results)
	structural = sum(result.mode == "structural" for result in results)
	failed = [result for result in results if not result.ok]

	print(f"Hands verified: {len(results)}")
	print(f"Exact replays: {exact}")
	print(f"Structural-only: {structural}")
	print(f"Failures: {len(failed)}")

	for result in failed:
		print(f"FAIL {result.hand_id} ({result.mode})")
		for error in result.errors:
			print(f"  - {error}")

	if failed:
		raise SystemExit(1)


if __name__ == "__main__":
	main()
