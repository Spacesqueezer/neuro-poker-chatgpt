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

## Phase 5 — Mathematical Agent

- equity calculation
- pot odds
- ranges
- Monte Carlo simulation

## Phase 6 — Learning System

Generated / curated data
        ↓
Imitation learning
        ↓
Self-play
        ↓
Reinforcement learning

## Phase 7 — Opponent Modeling

- persistent player profiles
- tendencies and statistics
- adaptive strategy inputs

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
