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
- Hand evaluation module foundation.

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
│   └── game_state.py
└── evaluation/
    ├── hand_rank.py
    └── evaluator.py
```

## Current focus

Hand comparison and kicker calculation.

Category-specific tiebreaker generation implemented for main hand types.

## Next steps

1. Seven-card hand evaluation.
2. Betting rounds.
3. Full Texas Hold'em game flow.
