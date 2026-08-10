# Current Limitations

This document lists known temporary constraints and verification boundaries.

## Betting and blinds

Supported:
- check, call, bet, raise, fold and all-in;
- minimum bets and full-raise sizing;
- short raises without incorrect action reopening;
- short all-in calls below the current target;
- dealer/SB/BB assignment and heads-up action order;
- automatic all-in board runout.

Known gaps:
- a player with fewer chips than the required SB/BB currently causes blind posting to reject hand start;
- cumulative short-raise reopen behavior needs broader deterministic coverage.

## Pot accounting

`Player.total_contribution` is the source of truth for hand-level contribution. `PotManager` supports:
- main pots;
- multiple side pots;
- folded contributors;
- unmatched refunds;
- ties in individual pot layers;
- deterministic odd-chip assignment.

Chip conservation must remain an invariant in every new pot/betting test.

## Table lifecycle

Busted-player removal is still performed by `tools/manual_hand.py` before the next debug hand. This is not the intended final architecture.

A future explicit table/seat component must own:
- funded/busted/inactive seat state;
- participation in the next hand;
- dealer-button movement across unavailable seats.

## Hand history and replay

Completed hands can be stored as JSONL HandHistory records.

- Seed-based random histories support exact replay through `HandReplayVerifier`.
- Histories from scripted scenarios currently have `seed=None`; they receive structural verification only.
- Exact replay compares the regenerated HandHistory payload (except the random hand id), including cards, actions, streets, pots and final stacks.

Commands:

```text
python tools/hand_history_viewer.py
python tools/verify_history.py
```

## Stress verification

`tools/stress_poker.py` creates independent seeded hands and chooses from legal actions using a minimal random smoke policy.

It currently verifies:
- hand termination;
- chip conservation;
- non-negative stacks;
- zero collected pot after terminal settlement;
- completed HandHistory;
- unique visible cards.

It is not an Arena and its random policy is not a poker strategy API.

Example:

```text
python tools/stress_poker.py --hands 10000 --seed 42
```

Any failure prints the exact hand seed before exiting.

## Manual verification

`python tools/manual_hand.py` starts a random default hand. Use `--seed N` to reproduce it exactly.

Named deterministic scenarios remain available through `--scenario NAME` or `scenario NAME` inside the runner.

The runner intentionally exposes all hole cards for engine debugging.
