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
- Named deterministic manual scenarios with fixed stacks, hole cards, board runouts and dealer position.
- Dealer button, small blind and big blind assignment.
- Automatic blind posting at hand start.
- Correct preflop and postflop first-action order, including heads-up rules.
- Dealer button rotation between hands.
- Showdown resolution, winner payout and equal-hand main-pot splitting.
- Automatic all-in board runout when no further betting decisions are possible.
- Busted-player removal in the manual runner before the next hand.
- Dedicated PotManager for main pots, multiple side pots, refunds, per-layer ties and odd-chip assignment.
- Deterministic cascade, folded-side-pot, side-pot-split and odd-chip manual scenarios.

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
│   ├── pot_manager.py
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

Complete edge-case betting and pot accounting before AI integration.

The basic hand lifecycle is playable from blinds through showdown and payout. The manual runner can load named deterministic scenarios whose stacks, cards, board runout and dealer position remain fixed across runs. This is now the preferred human smoke-test surface for edge cases.

Unequal-stack all-in accounting is now supported: short calls, returned unmatched chips, main pots and side pots are derived from per-player hand contributions.

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
- inspect HandController, BettingRound, BettingState and manual scenarios;
- preserve GameState -> Player -> Hand ownership;
- preserve blind/position rules, showdown payout and automatic all-in runout;
- use `python tools/manual_hand.py --scenario NAME` together with pytest.

1. Harden blind and stack edge cases.
   - Support short small-blind and big-blind all-ins instead of rejecting hand start.
   - Verify betting order when a blind player starts all-in.
   - Keep chip conservation explicit in tests.

2. Harden action reopening around multiple short all-ins.
   - Verify cumulative short raises versus one full raise.
   - Preserve per-player raise-lock semantics.
   - Add deterministic scenarios before expanding rules.

3. Continue table lifecycle work.
   - Move busted-player handling out of the manual runner into an explicit table/seat model.
   - Preserve dealer-button movement across removed seats.


## Hand history

Completed hands can now produce structured `HandHistory` records with blinds, actions, streets, showdown data, pot layers, and final stacks. The manual runner persists completed hands to `artifacts/hand_history.jsonl`; use `tools/hand_history_viewer.py` to inspect them.
