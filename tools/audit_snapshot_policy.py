"""Validate snapshot encoding/sizing on public simulated states, without training/inference."""

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from poker.api import ActionDecision, play_hand
from poker.game.actions import PlayerAction
from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_actions import decode, target
from poker.learning.snapshot_contract import RULESET, from_dict, from_public_state
from poker.learning.snapshot_encoding import LAYOUT, LAYOUT_SHA256, encode


class Probe:
    def __init__(self, seed, passive=False):
        self.random, self.passive = random.Random(seed), passive

    def choose_action(self, state, legal):
        if self.passive:
            action = (
                PlayerAction.CHECK if PlayerAction.CHECK in legal.actions else PlayerAction.CALL
            )
            return ActionDecision(action)
        action = self.random.choice(legal.actions)
        if action in (PlayerAction.BET, PlayerAction.RAISE):
            lo, hi = (
                (legal.min_bet, legal.max_bet)
                if action == PlayerAction.BET
                else (legal.min_raise_to, legal.max_raise_to)
            )
            return ActionDecision(action, self.random.choice((lo, hi, (lo + hi) // 2)))
        return ActionDecision(action)


def audit(output, hands=600, seed=51000):
    if hands <= 0 or (output.exists() and any(output.iterdir())):
        raise ValueError("Positive hand count and empty output directory required")
    output.mkdir(parents=True, exist_ok=True)
    counts, blockers, streets, sizes, actions = (
        Counter(),
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    with (output / "observations.jsonl").open("w", encoding="utf-8") as log:
        for index in range(hands):
            count, bb = 2 + index % 6, (2, 4, 10)[(index // 6) % 3]
            names = [f"seat_{s}" for s in range(count)]
            hand_seed = seed + index
            agents = {
                name: Probe(hand_seed * 17 + n, index % 3 == 0) for n, name in enumerate(names)
            }
            stacks = {
                name: (20, 50, 100, 250)[(index + n) % 4] * bb for n, name in enumerate(names)
            }

            def observer(state, legal, decision, *, hand_seed=hand_seed, bb=bb, count=count):
                counts["observed"] += 1
                snapshot = from_public_state(
                    state,
                    legal,
                    hand_id=f"audit:{hand_seed}",
                    observation_id=str(counts["observed"]),
                    big_blind=bb,
                    ruleset=RULESET,
                )
                reasons = snapshot.blocking_reasons()
                if reasons:
                    blockers.update(reasons)
                    counts["rejected"] += 1
                    if set(reasons) - {"existing_all_in_unsupported"}:
                        raise AssertionError(f"Unexpected engine refusal: {reasons}")
                    return
                encoded = encode(snapshot)
                restored = from_dict(json.loads(json.dumps(snapshot.to_dict())))
                assert encode(restored) == encoded
                for action_index, action in enumerate(ACTIONS):
                    if not snapshot.legal["actions"][action]:
                        continue
                    for fraction in (0.0, 0.5, 1.0):
                        result = decode(snapshot, action_index, fraction)
                        amount = (
                            result.amount_to
                            if result.amount_to is not None
                            else (result.call_delta or 0)
                        )
                        assert legal.allows(PlayerAction(action), amount)
                        _, label, _ = target(snapshot, action, result.amount_to)
                        assert decode(snapshot, action_index, label) == result
                        counts["legal_decodes_checked"] += 1
                counts["accepted"] += 1
                streets[state.street] += 1
                sizes[count] += 1
                actions[decision.action.value] += 1
                log.write(json.dumps(snapshot.to_dict(), ensure_ascii=False) + "\n")

            play_hand(
                agents,
                hand_seed,
                small_blind=bb // 2,
                big_blind=bb,
                starting_stacks=stacks,
                dealer_name=names[index % count],
                decision_observer=observer,
            )
    sources = [Path(__file__), *Path("src/poker/learning").glob("snapshot_*.py")]
    result = {
        "purpose": "contract_validation_not_training",
        "hands": hands,
        "seed": seed,
        "counts": dict(counts),
        "blockers": dict(blockers),
        "streets": dict(streets),
        "table_sizes": dict(sizes),
        "probe_actions": dict(actions),
        "layout": LAYOUT,
        "layout_sha256": LAYOUT_SHA256,
        "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "training_run": False,
        "policy_called": False,
        "player_db_written": False,
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hands", type=int, default=600)
    parser.add_argument("--seed", type=int, default=51000)
    args = parser.parse_args()
    result = audit(args.output, args.hands, args.seed)
    print(
        json.dumps(
            {k: result[k] for k in ("hands", "counts", "streets", "table_sizes", "blockers")}
        )
    )


if __name__ == "__main__":
    main()
