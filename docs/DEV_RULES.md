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

## Git commit rules

A successfully applied patch MUST create a git commit automatically.

Manual commits after successful patch application are not part of the workflow.

The patch process is considered incomplete if:
- files were changed but no commit was created;
- the working tree remains dirty after successful validation.

Every successful patch commit must:
- include only changes from the current patch;
- use an automatic commit message identifying the patch;
- report the created commit hash in the patch result.

The next patch must start from a clean git working tree created by the previous successful patch.

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
