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

