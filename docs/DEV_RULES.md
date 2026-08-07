# Development Rules

This file is the single source of truth for AI-assisted development standards.

All future patches MUST follow this document.

## Source of truth

The repository is the source of truth. Do not rely on previous chat history.

Before creating a patch:

1. Read docs/DEV_RULES.md.
2. Read docs/PROJECT_STATE.md.
3. Inspect the current source tree.
4. Verify assumptions against the current snapshot.

## NeuroPatch format

Patch files are JSON.

Required fields:

- patch_id
- goal
- allowed_files
- operations
- validation
- git

Supported operations must be verified against tools/neuropatch.py.

Never invent unsupported operations.

A patch must be generated for the current snapshot.
Never generate patches based only on memory.

## NeuroPatch rules

All project changes must be delivered through NeuroPatch.

Supported operations must match the current patcher implementation.

Do not invent unsupported operations.

Typical supported operations:
- create_file
- replace
- delete_file

Every patch must:
- target existing project state;
- avoid speculative rewrites;
- include validation commands;
- update documentation when required.

## Documentation rules

Any patch that changes:
- architecture;
- project structure;
- completed features;
- current focus;
- next steps;

MUST update docs/PROJECT_STATE.md.

PROJECT_STATE.md synchronization is a mandatory development step.

## Project continuation rules

Next steps in PROJECT_STATE.md are instructions for the next AI developer.

They must include:
- affected files or systems;
- current architectural assumptions;
- implementation direction;
- migration risks;
- validation expectations.

Avoid vague instructions.

## Architecture rules

- Connect existing systems before creating new abstractions.
- Keep responsibilities separated.
- Avoid hidden dependencies.
- Temporary architecture must include migration notes.
- Do not perform partial migrations.

## Project documentation structure

DEV_RULES.md:
How changes are made.

PROJECT_STATE.md:
Current state and next AI instructions.

ARCHITECTURE.md:
System structure.

DECISIONS.md:
Reasons behind important choices.

ROADMAP.md:
Long-term direction.

## Rule file ownership

Do not create duplicate development rule files.

Legacy development rules must be migrated into DEV_RULES.md.


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
