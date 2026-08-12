# Current Limitations

This document lists known temporary constraints and verification boundaries.

## Betting and pots

The no-limit hand engine currently supports:
- check, call, bet, raise, fold and all-in;
- full and short blind posting;
- minimum bets and full-raise sizing;
- per-player cumulative short-all-in reopening;
- short all-in calls below the current target;
- main/side pots, folded contributors, refunds, ties and odd chips;
- automatic all-in board runout.

`Player.total_contribution` remains the source of truth for hand-level pot accounting. Chip conservation is a mandatory invariant.

## Table lifecycle

Persistent lifecycle is owned by `Table` / `Seat`, not debug tooling.

Supported seat states:
- `ACTIVE`;
- `SITTING_OUT`;
- `BUSTED`.

Not yet modeled:
- rebuy/top-up;
- joining/leaving an occupied table session;
- waiting-for-BB/cash-room posting rules;
- tournament blind schedules.

## Public agent/simulation API

`poker.api` is now the supported external hand boundary.

`HandStateView` intentionally exposes:
- public player stacks/bets/contributions/positions;
- board, pot, street and target;
- only the acting player's hole cards.

`LegalActions` exposes legal action kinds plus call amount and bet/raise sizing bounds. `play_hand()` validates the returned `ActionDecision` before passing it to `HandController`.

Current boundary limitations:
- one `play_hand()` call still creates one independent table/hand;
- callers may provide either one shared `starting_stack` or explicit per-player `starting_stacks`;
- persistent multi-hand stack ownership belongs to `ArenaSession`, while richer session statistics are still being expanded.

External agents must not import `HandController`, `GameState` or `BettingRound`.

## Hand history and replay

- Seed-based random histories support exact replay through `HandReplayVerifier`.
- Scripted scenario histories have `seed=None` and receive structural verification only.
- Exact replay compares regenerated cards, actions, streets, pots and final stacks.

Commands:

```text
python tools/hand_history_viewer.py
python tools/verify_history.py
```

## Arena session lifecycle

`ArenaSession` now passes current per-player stacks into each new `play_hand()` call and accepts the returned final stacks only after validating player identity, non-negative stacks and chip conservation.

A session ends before another hand starts once any player reaches zero chips.

Still not modeled:
- rebuy/top-up during an Arena session;
- adding/removing players mid-session;
- persistent physical Table/Seat reuse across Arena hands;
- tournament blind schedules and elimination orchestration.

## Player statistics

Current limitation:
- statistics collection still requires mapping real HandHistory fields into the internal event contract;
- SQLAlchemy persistence for players, aggregate statistics and agent-specific opponent memory is implemented and SQLite-tested;
- Alembic owns schema evolution and the initial persistence revision is upgrade/downgrade tested;
- real PostgreSQL integration coverage is opt-in and requires `POKER_TEST_DATABASE_URL`; it is skipped in environments without a disposable PostgreSQL test database;
- richer tracker metrics such as fold-to-3-bet, c-bet and positional splits are not yet represented in the persistence schema.

## Stress verification

`tools/stress_poker.py` now exercises `poker.api.play_hand()` with a random smoke policy. It is still verification tooling, not an Arena strategy benchmark.

It checks termination, chip conservation, non-negative final stacks, completed history and unique visible cards.

```text
python tools/stress_poker.py --hands 10000 --seed 42
```

## Manual verification

`python tools/manual_hand.py` starts a random default hand. Use `--seed N` for exact reproduction.

Named deterministic scenarios remain available through `--scenario NAME` or `scenario NAME`.
