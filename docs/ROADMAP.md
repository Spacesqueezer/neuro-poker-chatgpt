# Neuro Poker Roadmap

## Phase 0 — Foundation ✅

- project structure
- NeuroPatch workflow
- Ruff / Pyright / Pytest / coverage configuration
- development documentation

## Phase 1 — Poker Domain Core ✅

- cards and deck
- player hand and board
- hand evaluation
- seven-card comparison
- positions foundation

## Phase 2 — Game Engine ✅

- betting rounds
- dealer button and blinds
- short blinds and cumulative short-all-in reopening
- all-ins and street progression
- main/side pots and refunds
- showdown and payout
- persistent Table/Seat lifecycle

## Phase 3 — Deterministic Verification & Public Simulation API ✅

- seeded random dealing
- deterministic scenarios
- structured HandHistory
- history viewer and replay verification
- randomized stress verification
- `HandStateView`
- `LegalActions`
- `ActionDecision`
- headless `play_hand()`
- stress runner migrated to the public simulation boundary

## Phase 4 — Baseline Agents & Arena 🟡 active

Build only against `poker.api`.

Implemented baseline agents:
- Random Agent
- Calling Station
- Nit

Still planned:
- TAG
- LAG
- Maniac

Arena v1 currently provides:
- deterministic seeds;
- fair dealer-position rotation;
- persistent per-player stacks across hands;
- session termination on bust;
- profit/loss foundations;
- hand failure accounting;
- chip-conservation validation at the session boundary.

Still required before Phase 4 is complete:
- bb/100;
- showdown/uncontested counts;
- richer crash reporting with exact failing seed;
- longer reproducible baseline-vs-baseline validation.

Do not start neural training before Arena can run long baseline-vs-baseline matches reproducibly.

## Phase 5 — Statistics & Opponent Modeling Foundation 🟡 active

Before neural training, the project must support persistent player statistics.

Goals:
- player profile generation;
- poker tracker style statistics;
- VPIP/PFR/aggression/showdown metrics;
- historical hand statistics;
- opponent memory storage.

Planned storage:
- local database for development;
- PostgreSQL for persistent experiments.

Generated player pool:
- approximately 100 persistent simulated opponents;
- different playing styles;
- stable identities across sessions.

## Phase 6 — Learning System

Teacher / solver data
        ↓
Imitation learning
        ↓
Self-play
        ↓
Reinforcement learning

Current direction:
- use a deterministic Monte-Carlo equity expert as the first meaningful teacher;
- record teacher-only labels while baseline agents provide varied opposition;
- benchmark the teacher before treating imitation learning as an improvement path;
- a deterministic tabular CFR core now exists on a deliberately tiny Kuhn-poker game to validate regret matching, information-set accounting and average-strategy accumulation independently of the production Hold'em engine;
- a generic two-player solver-game interface and restricted heads-up Hold'em adapter now sit above the tabular CFR core, using weighted explicit deals, the real seven-card evaluator and a small preflop fold/call/fixed-raise/shove abstraction; external-sampling MCCFR updates both players and samples weighted initial chance nodes reproducibly; solver nodes distinguish street/public-board visibility and support flop/turn/river check-through plus a finite postflop bet/fold/call/one-raise tree; preflop raise, ordered postflop bet sizes and the single raise increment live in `HoldemActionAbstraction`; solver nodes track player commitments and player-specific starting-stack caps explicitly, including asymmetric stacks and short commitment caps; exhausted stacks prune meaningless/duplicate betting branches, suppress raises/over-shoves against already all-in opponents, and closed all-in sequences run directly to fixed-board showdown instead of creating fake later-street decisions; focused MCCFR regression covers the expanded tree and the opt-in `tools/benchmark_mccfr.py` quality harness exposes explicit equal `(20, 20)` and asymmetric `(8, 20)` scenarios with versioned JSON containing resolved stack configuration, checkpoint strategy drift, runtime and throughput; trained average strategies have deterministic safe JSON export, strict import validation and exact information-set lookup; `RestrictedSolverPolicy` reconciles lookup results with live legal actions and uses explicit uniform deterministic fallback semantics; a solver-local full-tree evaluation harness measures exact/reconciled coverage and fallback behavior from exported artifacts without training or Arena; an opt-in small train→export→reload→coverage smoke command now exercises the complete artifact pipeline for equal and asymmetric stacks; next expand the restricted chance space with a small explicit weighted multi-deal benchmark while preserving imperfect-information and artifact boundaries.

## Phase 7 — Advanced Opponent Memory

- persistent player profiles
- agent-specific opponent statistics
- tendencies and statistics
- adaptive strategy inputs
- confidence-weighted observations

## Phase 8 — External State Extraction

Only after the internal simulation/agent stack is stable:
- card recognition
- stacks
- actions
- positions
- pot size

Vision must remain separate from poker decisions.

## Phase 9 — Advanced Strategy

- exploitative play
- tournament mode
- advanced opponent adaptation
