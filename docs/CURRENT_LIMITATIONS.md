# Current Limitations

This file describes known temporary constraints and architectural risks.

## Player model

GameState now stores full Player entities. Hole cards belong to each player's nested Hand:

GameState
 └── Player
      └── Hand

Dealer resets per-hand Player state before dealing new hole cards.

Remaining player-model work belongs to betting integration rather than ownership migration.

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
