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

Core runtime ownership:

```text
GameState
├── Deck
├── Board
├── BettingState
├── RoundManager
├── TurnOrder
└── Player[]
    └── Hand
```

GameState stores Player entities, not bare Hand objects.
Hole cards are owned by `Player.hand`.
Betting and action systems operate on the same Player entities used by turn order and dealing.


## Hand Flow Coordination

`HandController` coordinates one active hand:

```text
HandController
├── Dealer
├── ActionResolver
└── BettingRound
     └── Player[]
```

Responsibilities:
- `HandController` owns betting-round lifecycle and street progression.
- `ActionResolver` applies a validated player action to Player state.
- `BettingRound` tracks who still owes action and reopens action after a bet increase.
- `TurnOrder` selects the acting Player and skips folded players.
- `BettingState` stores the accumulated pot and current street target bet.

Completed betting rounds collect each `Player.current_bet` into the pot before the next street begins.
