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

Phase 2: Game Engine foundation.

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
- GameState stores full Player entities with nested Hand state.
- Betting state and pot foundation.
- Player turn order foundation with folded-player skipping.
- Dealer card dealing flow foundation.
- HandController betting-round integration.
- Basic check, call, bet, raise, fold and supported all-in processing.
- Raises reopen action for previously acted players.
- Completed betting rounds collect contributions and advance streets automatically.
- Deterministic manual console hand runner in tools/manual_hand.py.
- Dealer button, small blind and big blind assignment.
- Automatic blind posting at hand start.
- Correct preflop and postflop first-action order, including heads-up rules.
- Dealer button rotation between hands.

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

tools/
└── manual_hand.py
```

## Current focus

Complete the playable Texas Hold'em hand before AI integration.

The engine can now run betting rounds through HandController, enforce turn order, reopen action after raises, collect street contributions into the pot and automatically deal the next street. A console runner allows manual inspection of a deterministic three-player hand.

The engine now includes position-aware blind posting and action order. The next missing terminal feature is showdown resolution and payout. Side pots remain intentionally deferred until the basic hand can resolve a winner and transfer the pot correctly.

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
- read DEV_RULES.md and CURRENT_LIMITATIONS.md;
- inspect HandController, BettingRound, BettingState and evaluation modules;
- preserve GameState -> Player -> Hand ownership;
- preserve raise action reopening and automatic street progression;
- use tools/manual_hand.py as a human-readable smoke test in addition to pytest.

1. Implement showdown resolution and main-pot payout.
   - Reuse the existing seven-card evaluation and comparison systems.
   - Evaluate only non-folded players.
   - Support a single winner and equal-hand split of the main pot.
   - Keep side pots out of scope for this step.
   - Define deterministic handling for indivisible split-pot remainder chips.
   - Add tests covering winner payout, tied payout and folded-player exclusion.

2. Improve manual verification.
   - Extend tools/manual_hand.py to print showdown hand values and awarded chips after resolver integration.
   - Keep the runner deterministic by default.

3. Preserve and extend position/blind rules.
   - Dealer button rotates at each new hand.
   - Heads-up uses BTN=SB, with BTN acting first preflop and BB first postflop.
   - Multi-player preflop action starts left of BB; postflop action starts left of BTN.
   - Add named non-blind positions only when table-size semantics are needed.

4. Side pots and short all-ins.
   - Design contribution accounting only after the main-pot hand flow is stable.
   - Remove the current short-all-in rejection when side-pot accounting is implemented.
