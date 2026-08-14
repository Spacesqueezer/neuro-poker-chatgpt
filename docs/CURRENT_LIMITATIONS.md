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
- Player-position metadata is also compared for histories that recorded it; older seeded histories without `players[].position` remain exact-replay compatible by comparing the historical schema they actually contain.

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
- real `HandHistory` action/showdown events now feed VPIP, PFR, basic 3-bet and showdown statistics directly, while legacy pre-aggregated hand dictionaries remain supported;
- 3-bet and fold-to-3-bet now track explicit opportunities from preflop action order;
- flop continuation-bet opportunity/action and postflop aggression-factor inputs are derived from history;
- c-bet and fold-to-cbet currently cover the flop only;
- VPIP/PFR/3-bet positional splits are implemented and persisted for canonical 2-9 handed table positions;
- aggression inputs and aggression factor are available globally and separately for flop/turn/river;
- tracker numerators/denominators for VPIP, PFR, 3-bet, fold-to-3-bet, c-bet, aggression and showdown metrics are persisted in the SQLAlchemy/PostgreSQL statistics schema;
- Arena automatically collects successful hand histories and can persist them through `StatisticsService`; stable player records are resolved or created by unique player name, while generic non-Arena simulation callers still need to invoke the persistence bridge explicitly;
- SQLAlchemy persistence for players, aggregate statistics and agent-specific opponent memory is implemented and SQLite-tested;
- Alembic owns schema evolution and the initial persistence revision is upgrade/downgrade tested;
- real PostgreSQL integration coverage is opt-in and requires `POKER_TEST_DATABASE_URL`; it is skipped in environments without a disposable PostgreSQL test database;
- turn/river barrel frequencies, fold-to-turn/river-bet and other advanced tracker metrics are not yet modeled;
- persisted tracker data now feeds a fixed learning-observation boundary, but no trainable policy consumes it yet;
- `LearningObservationEncoder` supports 2-9 handed tables and pads unused opponent slots to a fixed shape;
- opponent information scope is explicit: `private` exposes only agent-specific memory, `global` exposes shared persisted tracker statistics, and `combined` exposes both;
- legal actions now have a stable six-action mask plus normalized call/bet/raise sizing bounds, and chosen decisions can be encoded as supervised targets;
- versioned `LearningSample` records can now be captured automatically from validated `play_hand()`/Arena decisions and persisted as JSONL;
- the dataset analyzer validates version, legal targets and vector shapes and reports basic action/player distributions;
- reproducible dataset generation is available through `LearningDatasetGenerator` and `tools/generate_dataset.py`, with deterministic seeds, train/validation JSONL splits and a manifest containing shape/action/player analysis;
- dataset generation fails fast if Arena reports failed hands; `RandomAgent` now generates legal sizing for BET/RAISE through `LegalActions`;
- the standalone generator currently supports baseline `random`, `calling_station` and `nit` agent specs and deliberately uses global tracker scope; online updates of agent-specific private memory during simulation are not yet implemented;
- train/validation splitting is deterministic sample-level splitting, not grouped by hand/session, so leakage-sensitive experiments may require a grouped splitter later;
- `ExpertAgent` provides deterministic Monte-Carlo equity/pot-odds teacher decisions through the public API, and dataset generation can record only the configured teacher's decisions;
- the expert is intentionally heuristic and is not claimed to be GTO: opponent holdings are sampled from an explicit normalized combo distribution conditioned on position, `OpponentRangeState`, board interaction and optional persisted `OpponentProfile`; profile influence is confidence/sample-size weighted, including positional VPIP/PFR/3-bet, street aggression and optional agent-memory estimates, but board-texture-specific frequencies, blocker effects beyond impossible-card removal, explicit Bayesian normalization and strategic action-tree lookahead beyond showdown equity/pot odds remain limited;
- reproducible teacher benchmarks now run multiple reset Arena sessions against Random/CallingStation/Nit and aggregate Expert profit, bb/100, failures and completion rate; this measures empirical strength but is not an exploitability/GTO metric;
- a deterministic tabular CFR implementation now exists under `poker.solver` behind a generic two-player extensive-form interface; Kuhn poker remains the correctness harness and a restricted heads-up Hold'em push/fold adapter now exercises real cards, weighted explicit private deals and the production seven-card evaluator while keeping hidden cards out of information sets; full Hold'em chance enumeration, multi-street bet sizing, MCCFR sampling and production-agent integration are still intentionally out of scope;
- no trainable policy consumes the learning samples yet; solver-backed teacher data and stronger benchmark evidence remain prerequisites before imitation learning is treated as a strength-improving step.

## Stress verification

`tools/stress_poker.py` now exercises `poker.api.play_hand()` with a random smoke policy. It is still verification tooling, not an Arena strategy benchmark.

It checks termination, chip conservation, non-negative final stacks, completed history and unique visible cards.

```text
python tools/stress_poker.py --hands 10000 --seed 42
```

## Manual verification

`python tools/manual_hand.py` starts a random default hand. Use `--seed N` for exact reproduction.

Named deterministic scenarios remain available through `--scenario NAME` or `scenario NAME`.
