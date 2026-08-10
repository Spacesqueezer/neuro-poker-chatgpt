# Project State

## Current milestone

Phase 3: deterministic verification and simulation hardening.

The Texas Hold'em hand engine is playable and stress-tested. Persistent table seats now own participation between hands, so debug tooling no longer deletes busted players or owns dealer-button continuity.

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
- `GameState.players` is the participant view for the current/next hand, not the persistent seating model.
- Busted and sitting-out seats remain at the table but are excluded when the next hand is prepared.
- Dealer button advances over unavailable seats while preserving physical seat order.
- Sit-out/sit-in changes apply to the next hand and do not mutate an already active hand.

### Verification

- Deterministic named manual scenarios.
- Random default hands with reproducible seeds.
- Structured `HandHistory` and JSONL persistence.
- Interactive history viewer.
- Exact seed-based replay verification.
- Structural verification fallback for scripted histories.
- Randomized stress runner with chip/card/termination invariants.

## Architecture snapshot

```text
Table
└── Seat[]
    ├── status
    └── Player
        └── Hand

GameState
├── Table
├── players[]  <- current hand participant view
├── Deck
├── Board
├── BettingState
├── RoundManager
└── TurnOrder

HandController
├── Dealer
├── ActionResolver
├── BettingRound
├── PotManager
└── HandHistory
```

## Known gaps

- No stable headless agent-facing hand API yet.
- No legal-action/state observation interface intended for agents.
- Arena, baseline agents and long-run poker statistics are not implemented.
- Scripted manual scenarios have no replay seed, so they receive structural rather than exact replay verification.
- Table rebuy/top-up, joining/leaving seats and cash-game session rules are intentionally not implemented yet.

## Next milestone

Promote hand execution into a stable headless simulation API without coupling the poker engine to AI implementations.

### 1. Introduce a legal-action/state interface

Direction:

```text
HandStateView
├── acting player
├── street / board
├── stacks / contributions
├── pot / current target
├── positions
└── legal actions + sizing bounds
```

The interface must expose enough information for agents without giving them hidden opponent hole cards.

### 2. Introduce a headless hand runner

Direction:

```text
play_hand(table, policies, seed) -> HandHistory / HandResult
```

The runner should coordinate policies through the public legal-action interface rather than through `HandController` internals.

### 3. Add baseline policies

Start with behavior used for verification rather than strategy quality:
- Random;
- Calling Station;
- Nit.

### 4. Build Arena only after the public simulation boundary is stable

Before Arena work, keep running:

```text
python -m pytest -q
python tools/stress_poker.py --hands 10000 --seed 42
python tools/verify_history.py
```

Any random stress failure must report the exact seed.

## AI bootstrap instructions

Before changing the project:

1. Read `docs/DEV_RULES.md`.
2. Read this file.
3. Read `docs/CURRENT_LIMITATIONS.md`.
4. Read `docs/ARCHITECTURE.md`.
5. Inspect the current source tree.

The repository is the source of truth. Do not rely on previous conversation history.

Every patch that changes architecture, capabilities, current focus or next steps MUST update this file.
