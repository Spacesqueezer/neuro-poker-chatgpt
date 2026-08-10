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

