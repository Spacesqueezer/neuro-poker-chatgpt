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

Note: the current GameState player collection temporarily uses Hand objects as participants. Migration to full Player entities must update betting, actions and controllers together.

## Development rules reference

Project development standards are defined in docs/DEV_RULES.md.

Every patch MUST follow DEV_RULES.md as the project development standard.

## Documentation synchronization rule

Every patch that changes project structure, architecture, completed features or next steps MUST update this file. This reminder must be preserved and copied forward into future PROJECT_STATE.md versions to prevent documentation drift.

## Next steps

The following instructions are written for the next AI developer.

Before implementing the next step:
- read DEV_RULES.md;
- inspect current architecture;
- verify that the current GameState player model is still based on temporary Hand objects;
- avoid migrating to Player entities partially.

1. Connect betting rounds with HandController.
   - Integrate BettingRound lifecycle into the existing hand flow.
   - Connect actions, turn order and street transitions.
   - Keep the temporary Hand-based participant model in mind.

2. Side pots and all-in handling.
   - Design this only after betting flow is stable.
   - Consider future Player entity migration before finalizing chip ownership.

3. Full Texas Hold'em game flow.
   - Build on existing Dealer, RoundManager, HandController and betting systems.
   - Preserve test coverage after every architectural change.
