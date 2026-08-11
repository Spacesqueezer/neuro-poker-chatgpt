# Project State

## Current milestone

Phase 3 is complete: deterministic verification now exercises the same public hand boundary intended for agents.

The next milestone is Phase 4: baseline agents and Arena v1.

## Current capabilities

### Poker hand engine

- 52-card deck, hole cards and community board.
- Seven-card Texas Hold'em evaluation and comparison.
- Dealer button, SB/BB, heads-up order and street progression.
- Check, call, bet, raise, fold and all-in actions.
- Minimum bet/full-raise sizing, short blinds and cumulative short-all-in reopen semantics.
- Per-player contributions, main/side pots, unmatched refunds, ties and deterministic odd chips.
- Automatic all-in runout, uncontested payout and showdown settlement.

### Table lifecycle

- Persistent `Table` with stable `Seat` objects.
- Explicit `ACTIVE`, `SITTING_OUT` and `BUSTED` seat states.
- `GameState.players` is the participant view for the current/next hand.
- Dealer button skips unavailable seats while preserving physical seat order.

### Public simulation boundary

`poker.api` is the supported boundary for agent/simulation code:

```text
HandStateView
+ LegalActions
+ ActionDecision
        |
        v
play_hand(agents, seed, dealer_name=...) -> HandHistory
```

- `HandStateView` exposes public table/hand state plus only the acting player's hole cards.
- `LegalActions` exposes call amount and legal bet/raise target ranges.
- Agent decisions are checked against `LegalActions` and then still processed by `HandController`.
- `play_hand()` owns the headless hand loop and returns completed `HandHistory`.
- `dealer_name` allows Arena to rotate position fairly across independent hands.
- `tools/stress_poker.py` now consumes this public API instead of `HandController` internals.

### Verification

- Deterministic named manual scenarios.
- Random default hands with reproducible seeds.
- Structured `HandHistory` and JSONL persistence.
- Interactive history viewer.
- Exact seed-based replay verification.
- Structural verification fallback for scripted histories.
- Randomized stress runner using the public simulation API.

## Architecture snapshot

```text
Table / GameState / HandController
             |
             v
         poker.api
   ┌─────────┼──────────┐
   v         v          v
HandState  Legal     play_hand
  View     Actions       |
                        agents

HandHistory
├── viewer
├── replay verifier
└── stress verification
```

The poker engine does not import or depend on agents. Agent code depends only on `poker.api`.

## Known gaps

- Baseline strategy agents are implemented: RandomAgent, CallingStationAgent, NitAgent.
- Arena v1 execution exists and now has baseline opponents for evaluation.
- Arena reporting is being expanded with aggregated session statistics.
- Arena v1 accounting now tracks session stacks and player profit foundations.
- Arena session orchestration is being refined so stack lifecycle remains explicit.
- Arena session object now tracks lifecycle state for future multi-hand execution.
- ArenaSession is becoming the explicit owner of multi-hand session state.
- `play_hand()` currently models one independent hand with a shared starting stack value; multi-hand session stack persistence belongs to Arena/Table orchestration.
- Scripted manual scenarios have no replay seed and therefore receive structural rather than exact replay verification.
- Table rebuy/top-up, joining/leaving seats and cash-room session rules remain intentionally out of scope.

## Next milestone — Arena v1

### 1. Baseline agents

Implement against `poker.api` only:
- `RandomAgent`;
- `CallingStationAgent`;
- `NitAgent`.

Agents must never inspect `GameState`, `HandController`, opponent hole cards or deck internals.

### 2. Arena runner

Direction:

```text
ArenaRunner
├── rotates dealer positions
├── assigns deterministic hand seeds
├── calls play_hand()
├── aggregates stack deltas
└── reports failures with exact seed
```

Initial statistics:
- hands;
- profit/loss;
- bb/100;
- showdown vs uncontested counts;
- chip conservation / crashes.

Do not add neural models or dataset generation yet.

### 3. Verification requirements

Before and after Arena work run:

```text
python -m pytest -q
python tools/stress_poker.py --hands 10000 --seed 42
python tools/verify_history.py
```

Any randomized failure must report its exact seed.

## AI bootstrap instructions

Before changing the project:

1. Read `docs/DEV_RULES.md`.
2. Read this file.
3. Read `docs/CURRENT_LIMITATIONS.md`.
4. Read `docs/ARCHITECTURE.md`.
5. Inspect the current source tree.

The repository is the source of truth. Do not rely on previous conversation history.

Every patch that changes architecture, capabilities, current focus or next steps MUST update this file.
