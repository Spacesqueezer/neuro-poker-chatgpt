# Project State

## AI Bootstrap Instructions

This project is maintained through AI-assisted patches.

Before making any changes:

1. Read docs/DEV_RULES.md.
2. Read docs/PROJECT_STATE.md.
3. Read docs/CURRENT_LIMITATIONS.md.
4. Read docs/ARCHITECTURE.md.
5. Inspect the current source tree.

The repository documentation is the source of truth.
Do not rely on previous conversation history.


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
- GameState now stores full Player entities with nested Hand state.
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
│   ├── betting_round.py
│   ├── turn_order.py
│   ├── round_manager.py
│   ├── dealer.py
│   ├── hand_controller.py
│   ├── actions.py
│   └── action_resolver.py
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

The rules engine can evaluate hands, compare results, store full Player entities, deal cards into each player hand, track streets and process basic betting flow. The next stage is integrating actions, turn order and betting rounds into complete hand progression.

GameState player ownership now follows the target structure: GameState -> Player -> Hand. Dealer resets per-hand player state before dealing new hole cards.

## Development rules reference

Project development standards are defined in docs/DEV_RULES.md.

Every patch MUST follow DEV_RULES.md as the project development standard.

## Related documentation

Known temporary constraints:
docs/CURRENT_LIMITATIONS.md

## Documentation synchronization rule

Every patch that changes project structure, architecture, completed features or next steps MUST update this file. This reminder must be preserved and copied forward into future PROJECT_STATE.md versions to prevent documentation drift.

## Next steps

The following instructions are written for the next AI developer.

Before implementing the next step:
- read DEV_RULES.md;
- inspect current architecture;
- verify that GameState players are full Player entities and hole cards live in player.hand;
- preserve the GameState -> Player -> Hand ownership model.

1. Complete betting round integration with HandController.
   - Connect BettingRound lifecycle with ActionResolver and TurnOrder.
   - Ensure street transitions happen only after valid betting completion.
   - Use Player entities directly for actions and turn order.
   - Keep hole-card access through player.hand.

2. Side pots and all-in handling.
   - Design this only after betting flow is stable.
   - Build chip ownership and contributions on the existing Player entities.

3. Full Texas Hold'em game flow.
   - Build on existing Dealer, RoundManager, HandController and betting systems.
   - Preserve test coverage after every architectural change.
