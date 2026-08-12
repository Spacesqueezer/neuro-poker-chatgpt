# Neuro Poker Architecture

## System Layers

Computer Vision
        |
        v
State Extraction
        |
        v
Poker State Model
        |
        v
Strategy System
        |
        v
Decision Engine
        |
        v
Action Executor


## Separation Rules

Vision does not make decisions.

Poker engine does not know about AI.

AI does not depend on screenshots.

Every layer must be testable independently.

## AI Architecture

Recommended modular approach:

- State Encoder
- Hand Evaluation Module
- Opponent Model
- Strategy Network
- Decision Engine
- Memory System

## Poker Domain Ownership

Persistent seating and one-hand state are separate:

```text
Table
└── Seat[]
    ├── SeatStatus
    └── Player
        └── Hand

GameState
├── Table
├── Player[]  # participants in the current/next hand
├── Deck
├── Board
├── BettingState
├── RoundManager
└── TurnOrder
```

`Table` owns stable physical seats and dealer-button seat continuity between hands. `GameState.players` is a hand-participant projection derived from funded `ACTIVE` seats when a hand is prepared. Busted and sitting-out players remain seated but do not enter the next hand.

Hole cards are owned by `Player.hand`. Betting and action systems operate only on the current hand participant view.


## Hand Flow Coordination

`HandController` coordinates one active hand:

```text
HandController
├── Dealer
├── ActionResolver
├── BettingRound
│    └── Player[]
└── PotManager
```

Responsibilities:
- `HandController` owns betting-round lifecycle and street progression.
- `ActionResolver` applies a validated player action to Player state.
- `BettingRound` tracks who still owes action and reopens action after a bet increase.
- `TurnOrder` selects the acting Player and skips folded players.
- `BettingState` stores the accumulated pot and current street target bet.
- `PotManager` derives main/side pot layers from `Player.total_contribution` and settles each layer independently at showdown.

Completed betting rounds collect each `Player.current_bet` into the pot before the next street begins.


## Pot Accounting

Per-hand contribution is owned by `Player.total_contribution`; street-local commitment remains in `Player.current_bet`.

`PotManager` is the single settlement component for contested showdown money:

```text
Player.total_contribution[]
        |
        v
PotManager.build_layers()
        |
        +--> main pot
        +--> side pot 1
        +--> side pot N
        +--> unmatched refund
        |
        v
PotManager.settle()
```

Folded players still fund layers through their contribution but are removed from that layer's eligible winners. Ties are split per layer. Odd chips are assigned deterministically starting with the first tied winner left of the dealer button.

## HandHistory

`poker.game.hand_history` is the structured event record for a completed hand. `HandController` records domain events; persistence is handled separately by `HandHistoryStore`. Debug tooling may serialize histories to JSONL without making the poker engine depend on filesystem storage.

## Verification Layer

Verification tooling depends on the poker engine, never the reverse.

```text
HandHistory
    |
    +--> HandReplayVerifier
    |       +--> exact replay for seed-based hands
    |       +--> structural checks for scripted histories
    |
    +--> hand_history_viewer.py

HandController + Dealer
    |
    +--> stress_poker.py
            random legal actions
            invariant checks
```

`HandReplayVerifier` reconstructs seed-based hands from starting stacks, dealer position, blinds, seed and recorded actions. The replayed structured history must match the recorded history except for the generated hand id.

`stress_poker.py` is verification tooling, not an agent/Arena abstraction. Its legal-action policy must not become a dependency of the engine.

## Public Simulation Boundary

Agent and Arena code must use `poker.api`; it must not depend on hand-controller internals.

```text
Poker engine internals
        |
        v
poker.api
├── HandStateView
├── PublicPlayerView
├── LegalActions
├── ActionDecision
└── play_hand()
        |
        v
Agents / Arena
```

`HandStateView` contains public state and only the acting player's hole cards. `LegalActions` contains action availability and sizing bounds. `play_hand()` validates an agent decision against that query surface and then delegates mutation to `HandController`, which remains the source of truth for action execution.

This boundary prevents Arena, baseline agents and future learning systems from duplicating poker legality rules.

## Statistics Persistence

Statistics consumers depend on repository contracts, not on SQLAlchemy directly:

```text
StatisticsService / future NeuralAgent opponent model
                    |
                    v
            repository contracts
             /             \
            v               v
      in-memory         SQLAlchemy
                        repositories
                            |
                            v
                     SQLAlchemy Session
                            |
                            v
          players / player_statistics / agent_memory
```

`PlayerRecord`, `PlayerStatisticsRecord` and `AgentMemoryRecord` remain transport/domain records at the repository boundary. SQLAlchemy models are persistence-only objects. `AgentMemoryModel` uses `(agent_id, player_id)` as a composite primary key so each neural agent can maintain an independent view of the same opponent.

Completed engine histories feed statistics through a separate read-only mapping path:

```text
HandHistory
    |
    v
HandStatisticsMapper
    |
    v
per-player hand facts
    |
    v
HandStatisticsAdapter
    |
    v
StatisticsCollector
```

The mapper derives facts only from recorded public hand events; it does not inspect `GameState` or `HandController`. For compatibility, already-aggregated player dictionaries are accepted and their existing flags are preserved. This keeps statistics reproducible from persisted histories without breaking the earlier statistics input contract.

SQLite in-memory is the fast persistence test backend. PostgreSQL uses the same repository contracts and has an opt-in integration path driven by `POKER_TEST_DATABASE_URL`; that database must be disposable because the integration test resets it to Alembic `base` before upgrading to `head`. Alembic owns schema evolution through `migrations/`; `src/poker/statistics/database/migrations.py` is the programmatic upgrade/downgrade boundary. Runtime migration URLs may be supplied explicitly by callers or through `POKER_DATABASE_URL` in Alembic execution. Schema changes must be represented by revisions rather than leaking database concerns into statistics services.
