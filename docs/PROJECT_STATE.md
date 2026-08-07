# Project State

## Current step

Phase 1: Poker Domain Core.

## Completed

- Python package structure.
- Card model with symbol display.
- Deck model with 52 unique cards.
- Texas Hold'em player hand model.
- Community cards board model.
- Basic game state container.
- Game state connected with betting, turn order and round flow.
- Hand evaluation system.
- Hand comparison foundation.
- Category-specific tiebreaker generation.
- Seven-card hand evaluation.
- Player model with stack and betting state foundation.
- Betting state and pot foundation.
- Player turn order foundation.
- Dealer card dealing flow foundation.

## Current architecture

```text
src/poker/
├── cards/
│   ├── card.py
│   └── deck.py
├── hand/
│   └── hand.py
├── board/
│   └── board.py
├── game/
│   ├── game_state.py
│   ├── betting.py
│   ├── turn_order.py
│   └── dealer.py
├── player/
│   └── player.py
└── evaluation/
    ├── hand_rank.py
    ├── evaluator.py
    ├── evaluation_result.py
    ├── hand_value.py
    ├── comparator.py
    └── seven_card.py
```

## Current focus

Building complete hand flow with betting rounds.

The rules engine can evaluate hands, compare results, store player state, deal cards and track streets. The next stage is connecting actions and betting into complete rounds.

## Documentation synchronization rule

Every patch that changes project structure, architecture, completed features or next steps MUST update this file. This reminder must be preserved and copied forward into future PROJECT_STATE.md versions to prevent documentation drift.

## Next steps

1. Connect betting rounds with HandController.
2. Side pots and all-in handling.
3. Full Texas Hold'em game flow.
