# Current Limitations

This file describes known temporary constraints and architectural risks.

## Player model

Current GameState uses Hand objects as temporary participants.

Target architecture:

GameState
 └── Player
      └── Hand

Migration must update together:

- GameState
- BettingRound
- HandController
- ActionResolver
- tests

Do not perform partial migration.

## Betting flow

Current state:
- card dealing exists;
- hand evaluation exists;
- action system exists;
- betting round tracking exists;
- complete betting flow integration is incomplete.

Future work:
- connect ActionResolver;
- connect TurnOrder;
- process chips;
- implement pots;
- implement side pots.

## AI continuation rule

Before changing any limitation described here, update this file and PROJECT_STATE.md.
