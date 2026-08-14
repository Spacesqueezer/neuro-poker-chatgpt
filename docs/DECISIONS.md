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
Restricted Hold'em solver sizing is configured through `HoldemActionAbstraction` in big-blind units. The abstraction owns one preflop raise size and an ordered discrete tuple of postflop bet sizes. Each postflop size is represented by a distinct solver action such as `bet_1bb` or `bet_2bb`.

Reason:
Bet sizing determines solver tree shape and strategy meaning. Encoding each configured size as a distinct finite action lets CFR/MCCFR learn separate branches while keeping the abstraction independent from production no-limit betting internals. Ordering and uniqueness are validated so action identity remains deterministic across runs.


## ADR-009: Solver Commitments Are Player-Explicit

Date:
2026-08-14

Decision:
Restricted Hold'em solver nodes store public commitments separately for player 0 and player 1. `matched_stake` is only a derived compatibility view equal to the smaller commitment.

Reason:
A single shared matched-stake scalar cannot represent an outstanding bet, a future raise or asymmetric commitments. Player-explicit accounting preserves finite solver abstractions while providing enough public state for correct fold refunds, calls and later raise branches.


## ADR-010: Restricted Postflop Tree Allows One Raise

Date:
2026-08-14

Decision:
After a restricted postflop opening bet, the responder may fold, call or make exactly one raise. The raise matches the outstanding commitment and adds a positive configurable number of equal raise increments through `HoldemActionAbstraction.postflop_raise_increment_multiplier`. After that raise the original bettor may only fold or call; re-raises are excluded.

Reason:
A single finite raise branch exercises the player-explicit commitment model and gives CFR/MCCFR strategically meaningful bet/raise decisions without exploding the tree or importing production no-limit betting rules.


## ADR-011: Restricted Solver Stacks Are Player-Specific Public Caps

Date:
2026-08-14

Decision:
`RestrictedHeadsUpHoldemGame` keeps the existing scalar `starting_stack` as the backward-compatible equal-stack default and accepts optional `starting_stacks=(player0, player1)` for asymmetric games. The resolved two-player stack tuple is copied into each solver node and included in information sets. Every commitment-changing solver action is capped by the acting player's stack.

Reason:
Asymmetric stacks change legal investment and terminal matched stake, so one shared scalar is not sufficient state. Keeping stack caps explicit and solver-local allows short calls, unequal all-ins and unmatched-chip refunds to be represented without importing the production betting engine or hidden mutable state.


## ADR-012: Closed All-In Solver Betting Runs Directly To Showdown

Date:
2026-08-14

Decision:
When a restricted Hold'em betting sequence closes and either player's commitment has reached that player's public starting-stack cap, the solver marks the node as a terminal fixed-board showdown runout. It does not manufacture check actions on later streets. Legal-action generation removes actions that cannot increase commitment, collapses capped postflop bet sizes that reach the same target, suppresses raises or over-shoves against an already all-in opponent, and disallows raising an already all-in bettor.

Reason:
The restricted solver already knows the complete fixed board in its chance deal, while information sets reveal only cards public before a decision. Once no further betting decision is possible, artificial street actions add duplicate information sets and strategically meaningless branches. A terminal runout preserves showdown utility and card-visibility guarantees without importing production-engine all-in machinery.


## ADR-013: Solver Strategy Artifacts Serialize Information Sets Explicitly

Date:
2026-08-14

Decision:
Restricted-Hold'em MCCFR average strategies are exported through a versioned JSON boundary. Each information set is serialized field-by-field as acting player, that player's hole cards, public street/board/action history, commitments and starting stacks. Artifact metadata records solver/configuration details including seed, iterations, benchmark scenario, blinds and `HoldemActionAbstraction`.

Reason:
Generic tuple/repr serialization would be brittle and could accidentally expose fields that are not part of the public information boundary. Explicit serialization makes artifacts deterministic, reviewable and safe from opponent-hole-card leakage while keeping them independent from production agent classes.
