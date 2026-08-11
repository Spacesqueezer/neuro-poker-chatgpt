# PostgreSQL Statistics Schema

## Purpose

Store persistent poker history, aggregated statistics and agent-specific opponent memory.

## Core entities

### players

Persistent simulated or external player identity.

Fields:
- id
- name
- profile_id

### player_profiles

Generated opponent archetypes.

Fields:
- id
- style
- vpip_target
- pfr_target
- aggression
- bluff_frequency

### hand_history

Completed poker hands.

Fields:
- id
- created_at
- table_id
- seed

### hand_players

Player participation in a hand.

Fields:
- hand_id
- player_id
- position
- result

### player_statistics

Aggregated tracker-style statistics.

Fields:
- player_id
- hands
- vpip
- pfr
- three_bet
- aggression
- wtsd
- wsd

### agent_memory

Private opponent model for each neural agent.

Fields:
- agent_id
- player_id
- hands_observed
- vpip_estimate
- pfr_estimate
- aggression_estimate
- confidence

Different neural agents intentionally keep separate observations about the same player.
