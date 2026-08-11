# Project State

## Current milestone

Phase 4 baseline Arena work is complete.

Current focus:
- player statistics foundation;
- persistent opponent memory architecture;
- preparation for dataset generation.

A first statistics model, collector, extraction pipeline and storage boundary exist. Agent-specific opponent memory architecture is introduced. PostgreSQL persistence transition has started: repository boundaries are being prepared while existing in-memory storage remains the active runtime implementation. Service layer and facade continue to isolate consumers from future database migration.

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
- Arena v1 accounting tracks session stacks, player profit and bb/100 evaluation foundations.
- `ArenaSession` is the explicit owner of multi-hand session state and hand-to-hand stack transitions.
- `ArenaRunner` is reduced to orchestration while session execution lives in `ArenaSession`.
- `play_hand()` accepts either a shared `starting_stack` or per-player `starting_stacks`; Arena uses the latter to preserve stacks across hands.
- Arena stops a session before starting another hand once any player has busted.
- Arena validates player identity, non-negative stacks and chip conservation before accepting a hand result.
- Scripted manual scenarios have no replay seed and therefore receive structural rather than exact replay verification.
- Table rebuy/top-up, joining/leaving seats and cash-room session rules remain intentionally out of scope.

## Active milestone — Arena v1

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

## Player statistics direction

The project will eventually maintain poker-tracker style statistics.

Required concepts:
- VPIP;
- PFR;
- 3-bet frequency;
- fold to 3-bet;
- continuation bet frequency;
- aggression factor;
- WTSD;
- W$SD;
- positional statistics.

Statistics are not only global player data. Neural agents require separate opponent memory:

```text
NeuralAgent A
    |
    +-- statistics about Player X


NeuralAgent B
    |
    +-- statistics about Player X
```

The same opponent may have different observed histories for different agents.

## AI bootstrap instructions

Before changing the project:

1. Read `docs/DEV_RULES.md`.
2. Read this file.
3. Read `docs/CURRENT_LIMITATIONS.md`.
4. Read `docs/ARCHITECTURE.md`.
5. Inspect the current source tree.

The repository is the source of truth. Do not rely on previous conversation history.

Every patch that changes architecture, capabilities, current focus or next steps MUST update this file.
