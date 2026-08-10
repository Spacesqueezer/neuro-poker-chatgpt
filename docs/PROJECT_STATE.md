# Project State

## Current milestone

Phase 3: deterministic verification and simulation hardening.

The Texas Hold'em engine is playable from blind posting through betting, all-ins, side pots, showdown and payout. Current work is focused on proving that the engine remains correct under replay and randomized stress before agent/Arena development.

## Current capabilities

- 52-card deck, hole cards and community board.
- Seven-card Texas Hold'em evaluation and comparison.
- Full `Player` entities owned by `GameState`.
- Dealer button, SB/BB, heads-up order and street progression.
- Check, call, bet, raise, fold and all-in actions.
- Minimum bet/full-raise sizing and short-raise reopen handling.
- Per-player hand contributions.
- Main pot, multiple side pots, unmatched refunds, per-layer ties and deterministic odd chips through `PotManager`.
- Automatic board runout when betting is closed by all-ins.
- Uncontested payout and showdown settlement.
- Deterministic named manual scenarios.
- Random default hands with reproducible seeds.
- Structured `HandHistory` with actions, streets, pots, payouts and final stacks.
- JSONL history persistence and interactive history viewer.
- Exact replay verification for seed-based histories.
- Structural verification fallback for scripted histories without a seed.
- Randomized headless stress runner with chip/card/termination invariants.

## Architecture snapshot

```text
GameState
├── Deck
├── Board
├── BettingState
├── RoundManager
├── TurnOrder
└── Player[]
    └── Hand

HandController
├── Dealer
├── ActionResolver
├── BettingRound
├── PotManager
└── HandHistory

Verification tools
├── HandReplayVerifier
├── tools/verify_history.py
├── tools/stress_poker.py
├── tools/manual_hand.py
└── tools/hand_history_viewer.py
```

## Known gaps

- Short SB/BB all-ins are still rejected during blind posting.
- Multiple cumulative short raises need additional reopen-rule verification.
- Busted-player removal still belongs to the manual runner instead of an explicit table/seat lifecycle model.
- Scripted manual scenarios have no replay seed, so they receive structural rather than exact replay verification.
- There is no stable headless agent API yet; the stress runner owns a minimal random legal-action policy only for engine verification.
- Arena, baseline agents and long-run poker statistics are not implemented yet.

## Next milestone

Complete engine hardening, then introduce a headless simulation API.

### 1. Close remaining betting edge cases

Affected systems:
- `HandController`
- `BettingRound`
- blind posting
- deterministic manual scenarios

Work:
- support short SB/BB all-ins;
- verify first-to-act behavior when a blind starts all-in;
- add cumulative-short-raise reopen scenarios/tests;
- keep chip conservation explicit.

### 2. Move table lifecycle out of debug tooling

Affected systems:
- new table/seat lifecycle component;
- `GameState` integration;
- `tools/manual_hand.py` migration.

Work:
- represent funded, busted and inactive seats explicitly;
- move dealer button across unavailable seats correctly;
- stop deleting busted players directly inside the manual runner.

### 3. Promote simulation into a stable API

Direction:

```text
play_hand(players/agents, seed) -> HandHistory/HandResult
```

The engine must remain independent from AI implementations. Baseline agents should consume a legal-action/state interface rather than calling `HandController` internals directly.

### 4. Stress before Arena

Before Arena work, repeatedly run:

```text
python tools/verify_history.py
python tools/stress_poker.py --hands 10000 --seed 42
python -m pytest -q
```

Any random stress failure must report the exact hand seed so it can be reproduced manually.

## AI bootstrap instructions

Before changing the project:

1. Read `docs/DEV_RULES.md`.
2. Read this file.
3. Read `docs/CURRENT_LIMITATIONS.md`.
4. Read `docs/ARCHITECTURE.md`.
5. Inspect the current source tree.

The repository is the source of truth. Do not rely on previous conversation history.

Every patch that changes architecture, capabilities, current focus or next steps MUST update this file.
