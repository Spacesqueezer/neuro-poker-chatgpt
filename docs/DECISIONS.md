# Architecture Decisions

## ADR-001: Clean Project Restart

Date:
2026-08-07

Decision:
Start poker project from zero.

Reason:
Previous architecture accumulated excessive coupling.

## ADR-002: Deterministic Simulation

Decision:
All game simulations must support seed-based reproduction.

Reason:
Required for:
- debugging;
- training;
- evaluation;
- experiment comparison.

## ADR-003: Modular AI

Decision:
Use multiple specialized components instead of one giant model.

Reason:
Better debugging, evaluation and improvement.

## ADR-004: Player Owns Hand

Date:
2026-08-09

Decision:
GameState stores full Player entities, and each Player owns its Hand.

Reason:
Betting, action resolution, turn order and card dealing must operate on one participant model. Keeping bare Hand objects in GameState would split identity, chips and hole cards across incompatible representations.

## ADR-005: Reopen Betting by Amount Faced Since Last Action

Date:
2026-08-10

Decision:
In no-limit betting, a player who was locked by a short all-in regains the right to raise once the current target is at least one full minimum-raise increment above the target that player last acted on.

Multiple short all-ins may therefore cumulatively reopen action for one player while action remains locked for another player who acted later.

The minimum raise size itself remains the size of the last full valid bet or raise; cumulative short all-ins do not redefine it.

Reason:
This matches no-limit hold'em reopen semantics while keeping raise sizing and reopen eligibility as separate concepts.


## ADR-006: Persistent Table Owns Seats; GameState Exposes Hand Participants

Date:
2026-08-10

Decision:
`Table` owns stable `Seat` objects and dealer-button seat continuity between hands. `GameState.players` remains the ordered participant view used by the active hand engine and is rebuilt from funded `ACTIVE` seats before each new hand.

Seat status is explicit (`ACTIVE`, `SITTING_OUT`, `BUSTED`). A status change does not remove a player from a hand already in progress; it changes eligibility for the next hand.

Reason:
Physical seating lifetime and one-hand participant lifetime are different concerns. Keeping busted-player removal in `manual_hand.py` made debug tooling responsible for poker lifecycle rules and lost persistent seat identity. The projection approach preserves existing betting/evaluation code while moving lifecycle ownership into the domain model.


## ADR-007: Solver Game Boundary Before Full Hold'em Solving

Date:
2026-08-14

Decision:
CFR depends on a generic two-player extensive-form game interface rather than Kuhn-specific cards/history. The first Hold'em adapter is deliberately restricted to heads-up push/fold play over an explicit finite weighted set of private deals and a fixed public board.

The solver information set may contain only information available to the acting player. Hold'em showdown reuses the production seven-card evaluator, but the adapter does not import `HandController`, Arena or learning code.

Reason:
Full no-limit Hold'em has a state/action/chance space that is far too large for exhaustive tabular CFR. A small real-card adapter validates the solver boundary and hidden-information semantics before MCCFR/chance sampling and larger abstractions are introduced.


## ADR-008: Hold'em Solver Bet Sizing Is an Explicit Abstraction

Date:
2026-08-14

Decision:
Restricted Hold'em solver sizing is configured through `HoldemActionAbstraction` in big-blind units. The abstraction owns the single preflop raise size and single postflop bet size; traversal logic consumes those values but does not define them.

Reason:
Bet sizing determines solver tree shape and strategy meaning. Keeping it explicit allows controlled expansion to a small discrete sizing set without coupling the solver to production no-limit betting internals or silently changing the game being solved.
