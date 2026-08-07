# Development Rules

Current AI patch standards are maintained in docs/DEV_RULES.md.

Future patches MUST follow docs/DEV_RULES.md as the source of truth.

## Before Changes

- Analyze existing architecture.
- Use NeuroPatch for modifications.
- Avoid unnecessary files.
- Add tests.

## After Changes

Run:

- ruff
- pyright
- pytest
- coverage

## Coding Principles

- Small modules.
- Explicit interfaces.
- No hidden dependencies.
- Reproducible experiments.
