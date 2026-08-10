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

## Phase 2 — Game Engine ✅ foundation complete

Implemented:
- players and stacks
- betting rounds
- dealer button and blinds
- street progression
- all-ins
- main and side pots
- refunds
- showdown and payout

Hardened:
- short blind all-ins
- cumulative short-all-in reopen semantics

Still hardening:
- explicit table/seat lifecycle

## Phase 3 — Deterministic Verification 🟡 current

Implemented:
- seeded random dealing
- deterministic manual scenarios
- structured HandHistory
- JSONL history viewer
- exact seed-based hand replay verification
- structural verification for scripted histories
- randomized engine stress runner

Next:
- explicit table/seat lifecycle
- replay/stress larger corpora
- promote a stable headless `play_hand` simulation API

## Phase 4 — Baseline Agents

Create agents against a stable legal-action/state interface:
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
