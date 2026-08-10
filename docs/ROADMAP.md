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

Implemented and hardened:
- players and stacks
- betting rounds
- dealer button and blinds
- short blinds
- cumulative short-all-in reopening
- street progression and all-ins
- main/side pots and refunds
- showdown and payout
- persistent Table/Seat lifecycle
- busted and sitting-out seat skipping

## Phase 3 — Deterministic Verification 🟡 current

Implemented:
- seeded random dealing
- deterministic scenarios
- structured HandHistory
- history viewer
- exact seed-based replay
- structural scripted-history verification
- randomized stress runner

Current target:
- define a stable legal-action/state boundary;
- promote hand execution to a reusable headless API;
- stress that public boundary before Arena work.

## Phase 4 — Baseline Agents

Build policies only against the stable public simulation interface:
- random
- calling station
- nit
- TAG
- LAG
- maniac

Then add Arena statistics and long-run comparison.

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
