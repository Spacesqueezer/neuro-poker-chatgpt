# Current Limitations

This file describes known temporary constraints and architectural risks.

## Player model

GameState stores full Player entities. Hole cards belong to each player's nested Hand:

GameState
 └── Player
      └── Hand

Dealer resets per-hand Player state before dealing new hole cards.

## Betting flow

Current state:
- HandController owns the active BettingRound lifecycle;
- actions are processed through ActionResolver for the current TurnOrder player;
- checks, calls, bets, raises, folds and supported all-ins update player betting state;
- a raise reopens action for players who already acted;
- completed street contributions are collected into the pot;
- completed betting rounds automatically advance the street and deal community cards;
- folded players are skipped by turn order;
- a one-player remainder moves the hand to SHOWDOWN as a temporary terminal state.

Known limitations:
- blinds and dealer/button positions are not implemented;
- minimum raise sizing is not implemented;
- side pots are not implemented;
- short all-ins while facing a larger bet are rejected until side-pot accounting exists;
- showdown winner resolution and pot payout are not implemented;
- street action currently restarts from the first active player because position rules do not exist yet.

## Manual verification

`python tools/manual_hand.py` starts a deterministic three-player console hand.

Supported commands:
- check
- call
- bet N
- raise N
- fold
- all-in
- state
- quit

The tool intentionally exposes all hole cards for engine debugging.

## AI continuation rule

Before changing any limitation described here, update this file and PROJECT_STATE.md.
