# Neuro Poker Roadmap

## Phase 0 — Foundation

Status: Current

- Project infrastructure
- NeuroPatch
- Ruff
- Pyright
- Pytest
- Coverage
- Documentation
- Deterministic experiments

## Phase 1 — Poker Domain Core

Create pure poker rules.

Goals:
- cards
- deck
- combinations
- hand evaluation
- positions ✅ BTN/SB/BB foundation

No AI.

## Phase 2 — Game Engine

Implement:

- tables
- players
- betting rounds
- pots
- side pots
- showdown ✅ main-pot payout foundation

## Phase 3 — Deterministic Simulation

Required:

- seed-based generation
- reproducible hands
- hand replay
- scenario generation ✅ named deterministic manual scenarios foundation
- experiment tracking

## Phase 4 — Baseline Agents

Create:

- random agent
- nit
- TAG
- LAG
- maniac
- calling station

## Phase 5 — Mathematical Agent

Implement:

- equity calculation
- pot odds
- ranges
- Monte Carlo simulation

## Phase 6 — Learning System

Training pipeline:

Human-like data / generated data
        ↓
Imitation learning
        ↓
Self-play
        ↓
Reinforcement learning

## Phase 7 — Opponent Modeling

Database-backed player profiles.

## Phase 8 — Computer Vision

Extract:

- cards
- stacks
- actions
- positions ✅ BTN/SB/BB foundation
- pot size

## Phase 9 — Advanced Strategy

- exploitative play
- tournament mode
- advanced opponent adaptation
