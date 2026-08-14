# AI Development Workflow

## Purpose

This document explains how to continue AI-assisted development when previous chat context is unavailable.

The repository is the source of truth.

## Starting a new session

Before planning changes:

1. Check current git commit.
2. Read:
   - DEV_RULES.md
   - PROJECT_STATE.md
   - CURRENT_LIMITATIONS.md
   - ARCHITECTURE.md
   - DECISIONS.md
   - ROADMAP.md
3. Inspect current source files affected by the task.
4. Generate a patch only for the current repository state.

Do not reconstruct project state from previous conversations.

## Repository inspection

When repository access is available, the AI should inspect the repository directly.

The workflow assumes the AI can:
- read files;
- inspect structure;
- compare implementation with documentation;
- prepare a NeuroPatch transaction.

## NeuroPatch

All changes are delivered through NeuroPatch.

Patch structure:

```json
{
  "patch_id": "unique_name",
  "goal": "change description",
  "allowed_files": [],
  "operations": [],
  "validation": {},
  "git": {}
}
```

Operations must match the current `tools/neuropatch.py`.

Common rules:

- `create_file` only for files missing in the current repository.
- `replace` only for existing files.
- Never use files from failed patches as a source of truth.

## Validation

Every patch must include validation.

For isolated internal subsystem work, `DEV_RULES.md` permits a focused profile with explicitly named subsystem tests. Broader contracts still require fast/extended/full validation as defined there.

Typical project checks:

```text
python -m pytest -q
python tools/stress_poker.py --hands 10000 --seed 42
python tools/verify_history.py
```

## Documentation synchronization

Architectural changes require documentation updates.

Update:
- PROJECT_STATE.md for current state;
- ARCHITECTURE.md for structure;
- DECISIONS.md for important choices;
- ROADMAP.md for milestone changes.

## Current poker architecture boundary

```text
Poker engine
      |
      v
  poker.api
      |
      +--> Agents
      |
      +--> Arena
```

Agents and Arena must not depend on HandController internals.

## Continuing after context loss

Recommended first message:

"Read docs/DEV_RULES.md and docs/PROJECT_STATE.md. Inspect the current repository and continue from the latest successful commit."
