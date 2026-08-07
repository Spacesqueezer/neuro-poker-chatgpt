# Development Rules

This file is the single source of truth for AI-assisted development standards.

Every future patch MUST follow this document.

## Documentation requirements

1. Any patch that changes architecture, project structure, completed features, current focus or next steps MUST update docs/PROJECT_STATE.md.
2. PROJECT_STATE.md synchronization is a mandatory development step.
3. The synchronization rule must remain in PROJECT_STATE.md after updates.

## Project continuation requirements

Before creating any patch:

1. Read docs/DEV_RULES.md.
2. Read docs/PROJECT_STATE.md.
3. Inspect the current source tree.
4. Verify assumptions against the current snapshot.

Do not assume previous architecture if the current project differs.

## Project state requirements

1. Current focus must describe the real development stage.
2. Next steps are written primarily for the next AI developer.
3. Next steps must include:
   - affected systems;
   - files or modules involved;
   - architectural assumptions;
   - migration risks;
   - validation expectations.
4. Avoid vague instructions.

## Patch quality rules

1. Prefer small verified patches over speculative rewrites.
2. Every patch must include validation commands.
3. Tests must describe the intended architecture.
4. Preserve compatibility unless migration is explicitly planned.
5. Avoid unnecessary files and duplicate systems.

## Development workflow

After changes run:

- ruff
- pyright
- pytest
- coverage

## Architecture rules

1. Keep responsibilities separated.
2. Connect existing systems before creating new abstractions.
3. Use explicit interfaces.
4. Avoid hidden dependencies.
5. Temporary architecture must include migration notes.

## Reproducibility rules

Experiments, simulations and AI training workflows must be reproducible.

## Rule file ownership

Do not create additional development rule files.

If useful rules are discovered in old documents, migrate them into DEV_RULES.md.

DEV_RULES.md defines how changes are made.
PROJECT_STATE.md defines current project state.
