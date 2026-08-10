# Current Limitations

This document lists known temporary constraints and verification boundaries.

## Betting and pots

The current no-limit hand engine supports:
- check, call, bet, raise, fold and all-in;
- full and short blind posting;
- minimum bets and full-raise sizing;
- per-player cumulative short-all-in reopening;
- short all-in calls below the current target;
- main/side pots, folded contributors, refunds, ties and odd chips;
- automatic all-in board runout.

`Player.total_contribution` remains the source of truth for hand-level pot accounting. Chip conservation is a mandatory invariant.

## Table lifecycle

Persistent lifecycle is owned by `Table` / `Seat`, not by debug tooling.

Supported seat states:
- `ACTIVE`;
- `SITTING_OUT`;
- `BUSTED`.

Busted and sitting-out seats keep their physical seat positions but are excluded from the next hand. Dealer movement skips unavailable seats. A sit-out/sit-in request affects future hand participation and does not remove a player from a hand already in progress.

Not yet modeled:
- rebuy/top-up;
- joining or leaving an occupied table session;
- waiting-for-BB/cash-room posting rules;
- tournament blind schedules.

## Hand history and replay

- Seed-based random histories support exact replay through `HandReplayVerifier`.
- Scripted scenario histories have `seed=None` and receive structural verification only.
- Exact replay compares regenerated cards, actions, streets, pots and final stacks.

Commands:

```text
python tools/hand_history_viewer.py
python tools/verify_history.py
```

## Stress verification

`tools/stress_poker.py` is engine verification tooling, not an Arena or strategy API.

It checks:
- termination;
- chip conservation;
- non-negative stacks;
- zero collected pot after terminal settlement;
- completed HandHistory;
- unique visible cards.

Example:

```text
python tools/stress_poker.py --hands 10000 --seed 42
```

## Manual verification

`python tools/manual_hand.py` starts a random default hand. Use `--seed N` for exact reproduction.

Useful lifecycle commands:
- `table`;
- `sitout NAME`;
- `sitin NAME`;
- `deal`.

Named deterministic scenarios remain available through `--scenario NAME` or `scenario NAME`.

The runner intentionally exposes all hole cards for debugging.

## Agent boundary

There is no stable public agent API yet. External policies must not be built directly against `HandController` internals because the next milestone is a dedicated legal-action/state interface and headless hand runner.
