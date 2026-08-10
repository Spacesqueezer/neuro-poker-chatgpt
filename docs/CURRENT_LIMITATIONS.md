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
- check, call, bet, raise, fold and supported all-in actions are playable;
- minimum bet and full-raise sizing are enforced;
- short raises do not incorrectly reopen betting;
- blinds, dealer rotation and heads-up action order are implemented;
- completed rounds collect chips and automatically advance streets;
- when further betting is impossible because of all-ins, the board runs out automatically;
- showdown evaluates active players, pays a single winner or splits the main pot on ties;
- uncontested pots are paid immediately.

Known limitations:
- per-hand contribution accounting is not yet modeled independently of street bets;
- main/side pots are supported through per-player hand contribution levels;
- short all-in calls below the current target are supported;
- unmatched excess contribution is returned at settlement;
- short blind all-ins are not supported;
- manual busted-player removal is a debug-runner behavior, not yet a table/seat lifecycle model.

## Manual verification

`python tools/manual_hand.py` starts the deterministic `default` scenario.

A scenario can be selected at launch:

`python tools/manual_hand.py --scenario sidepot`

Or switched while the runner is open:
- `scenario list`
- `scenario headsup`
- `scenario minraise`
- `scenario short-allin`
- `scenario sidepot`
- `scenario splitpot`

Every named scenario fixes starting stacks, hole cards, future board runout and initial dealer position. The tool intentionally exposes all hole cards for engine debugging.

Supported play/debug commands:
- check
- call
- bet N
- raise N
- fold
- all-in / allin
- state
- players
- deal
- scenario list
- scenario NAME
- help
- quit

## AI continuation rule

Before changing any limitation described here, update this file and PROJECT_STATE.md.
