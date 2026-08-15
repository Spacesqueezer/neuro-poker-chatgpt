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
- a generic two-player solver-game interface and restricted heads-up Hold'em adapter now sit above the tabular CFR core, using weighted explicit deals, the real seven-card evaluator and a small preflop fold/call/fixed-raise/shove abstraction; external-sampling MCCFR updates both players and samples weighted initial chance nodes reproducibly; solver nodes distinguish street/public-board visibility and support flop/turn/river check-through plus a finite postflop bet/fold/call/one-raise tree; preflop raise, ordered postflop bet sizes and the single raise increment live in `HoldemActionAbstraction`; solver nodes track player commitments and player-specific starting-stack caps explicitly, including asymmetric stacks and short commitment caps; exhausted stacks prune meaningless/duplicate betting branches, suppress raises/over-shoves against already all-in opponents, and closed all-in sequences run directly to fixed-board showdown instead of creating fake later-street decisions; the opt-in benchmark includes single-deal `equal`/`asymmetric` scenarios plus a three-deal `weighted_multi` chance model with 5/3/2 weights and deliberately merged preflop information sets across hidden states; strategy artifact format v2 now binds every export to a versioned SHA-256 identity of the exact ordered weighted chance space and evaluation rejects incompatible games; trained average strategies otherwise retain deterministic safe JSON export, strict import validation and exact information-set lookup; `RestrictedSolverPolicy`, full-tree evaluation and end-to-end smoke remain solver-local with no production Arena integration; benchmark scenario configuration is now consolidated into immutable descriptors that own names, stacks, deal factories and chance-space identity while preserving CLI/artifact compatibility; next add a solver-local versioned teacher-record export from validated strategy artifacts before any connection to `poker.learning` or production agents.

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
