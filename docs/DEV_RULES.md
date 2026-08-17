# Development Rules

This file is the single source of truth for AI-assisted development standards.

All future patches MUST follow this document.

## Source of truth

The repository is the source of truth. Do not rely on previous chat history.

When repository access is available, AI must inspect the current repository instead of relying on memory or old snapshots.

Before creating a patch:

1. Read docs/DEV_RULES.md.
2. Read docs/PROJECT_STATE.md.
3. Inspect the current source tree.
4. Verify assumptions against the current repository state.

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

A patch must be generated for the current repository state.
Never generate patches based only on memory.

## NeuroPatch rules

All project changes must be delivered through NeuroPatch.

Supported operations must match the current patcher implementation.

Do not invent unsupported operations.

Supported top-level operations in the current `tools/neuropatch.py`:
- `create_file` with `file` and `content`;
- `replace` with `file`, `old`, and `new`;
- `delete_file` with `file`;
- `modify_file` with `file` and an `operations` list.

Inside `modify_file`, the current patcher supports only nested `replace` operations using `type`, `old`, and `new`.

Explicitly unsupported in the current patcher:
- nested `append` inside `modify_file`;
- nested `create_file` or `delete_file` inside `modify_file`;
- the legacy `changes` field for `modify_file`;
- `find` / `replace` pairs that are not expressed as nested `replace` operations;
- any invented operation type not implemented by `tools/neuropatch.py`.

To append text to an existing file, use a normal `replace` operation whose `old` anchor is exact current file content near the insertion point and whose `new` value contains the original anchor plus the appended text. Do not use an `append` operation unless the patcher is explicitly changed to support it.

Every patch must:
- target existing project state;
- avoid speculative rewrites;
- include validation commands;
- update documentation when required.

For `replace` operations, a mismatch report must identify the operation index, target file, match count and a short preview of the expected `old` text. Failed patches must be repaired from exact current repository state instead of guessing which replacement failed.

## Mandatory AI-side patch preflight

Before delivering any `.npatch.json` to the user, the AI MUST test the patch against the current repository state on its own side.

At minimum, preflight must:
- start from the current remote `ai-development` source, never from a failed transaction or old patch;
- apply or faithfully simulate every patch operation sequentially in patch order;
- verify that every `replace` operation matches exactly once at the moment it is applied;
- verify that all declared files and operation types are valid for the current NeuroPatch implementation;
- run the patch validation commands locally when the execution environment can run the repository;
- never deliver a patch that has not passed operation-application preflight.

If the execution environment cannot run the repository test suite, the AI must say so explicitly, but this does not waive operation-application preflight. A `Replace mismatch` caused by an untested anchor is an AI-side process failure and must not be delegated to the user as routine testing.

After any failed user-side patch run, assume NeuroPatch rollback restored the pre-patch repository state unless the failure report explicitly says a commit was preserved. Rebuild and preflight the next patch from fresh remote state rather than layering a repair over rolled-back feature code.

## Validation profiles

Validation commands are selected according to patch impact.

Default profile:

```text
fast
```

Runs after every patch:

```text
python -m pytest -q
```

Extended profile:

```text
extended
```

Runs when a patch affects shared contracts, architecture boundaries or complex internal logic:

```text
python -m pytest -q
python tools/verify_history.py
```

Full profile:

```text
full
```

Runs before milestone completion and after risky gameplay changes:

```text
python -m pytest -q
python tools/stress_poker.py --hands 10000 --seed 42
python tools/verify_history.py
```

AI generating NeuroPatches must choose the smallest sufficient profile.

Use `fast` for isolated utilities, tests, documentation and internal refactoring without changed public contracts.

Focused profile:

```text
focused
```

Runs only subsystem-specific tests plus cheap syntax/import checks when a patch is isolated behind an already-established internal boundary. The patch must name the exact test files or test directories in `validation.commands`.

Use `focused` for isolated solver, statistics, learning or tooling work when:
- production poker-engine behavior is untouched;
- the affected subsystem already has direct regression coverage;
- the patch does not change a cross-subsystem public contract;
- a later milestone/full validation still exists as a safety net.

Do not use `focused` for poker engine, hand lifecycle, pots/stacks, Arena, migrations, persistence schema, serialization compatibility or broad refactors.

Use `extended` for API changes, serialization changes, database changes, migration changes, shared domain models and agent interfaces.

Use `full` for poker engine changes, hand lifecycle, betting logic, stacks, pots, randomness, replay/history, Arena behavior and milestone patches.

The selected validation profile must be justified by the affected systems.

## Git commit rules

A successfully applied patch MUST create a git commit automatically.

Manual commits after successful patch application are not part of the workflow.

The patch process is considered incomplete if:
- files were changed but no commit was created;
- the working tree remains dirty after successful validation.

Every successful patch commit must:
- include only changes from the current patch;
- use an automatic commit message identifying the patch;
- report the created commit hash in the patch result;
- be pushed automatically to the upstream of the active working branch before the patch is reported as `SUCCESS`.

A local commit with a failed push is not a successful handoff. NeuroPatch must report the failure, preserve the local commit and archived patch, avoid pretending that rollback occurred after commit creation, and must not print `SUCCESS HANDOFF` until the push succeeds.

The next patch must start from a clean git working tree created by the previous successful patch.

AI-assisted development uses the active Git branch context. NeuroPatch applies patches on the current working branch, reports that branch in the transaction result, and pushes to its configured upstream after successful validation. `main` remains a human-controlled safety branch by workflow convention.

Every loaded patch is copied into its external NeuroPatch transaction directory immediately after transaction creation. Validation, archival and commit workflow must not depend on the original Downloads file remaining present during a long run. Every successfully committed patch file is archived in the tracked repository path `patches/applied/<patch_id>.npatch.json` from the transaction-local copy and the original Downloads file is removed only after the commit and push succeed. Failed patches remain in Downloads when still present for diagnosis or retry; the transaction-local copy is also retained with the transaction. Archived patches are provenance records; they do not replace the current repository state, `PROJECT_STATE.md` or source inspection as sources of truth.

After a successful patch, NeuroPatch prints a self-contained `SUCCESS HANDOFF` command addressed to the AI, not instructions for the user. The handoff text assumes the successful commit has already been pushed.

When the user sends that final `SUCCESS HANDOFF` line back to the AI, it means:
- the reported successful commit has been pushed to the active working branch upstream;
- the AI must inspect the freshly pushed working branch;
- the AI must re-read `DEV_RULES.md` and `PROJECT_STATE.md`;
- the AI must continue from the recorded next step;
- the AI must generate and attach the next `.npatch.json` file in the same response rather than merely describing what it plans to do.

The user does not need to restate the workflow or resend the complete success report unless additional diagnostic context is useful.

## Documentation rules

Any patch that changes:
- architecture;
- project structure;
- completed features;
- current focus;
- next steps;

MUST update docs/PROJECT_STATE.md.

PROJECT_STATE.md synchronization is a mandatory development step.

`docs/USER_GUIDE_RU.md` is the user-facing command and workflow reference.

Any patch that adds or changes:
- a CLI command;
- a command-line argument;
- an interactive user command;
- a tool under `tools/`;
- a user-visible output format;
- a required environment variable;
- a standard workflow for tests, benchmarks, dataset generation, migrations, training, snapshots or patch application;

MUST update `docs/USER_GUIDE_RU.md` in the same patch.

Internal APIs that require no user action do not need to be duplicated in the user guide.

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

USER_GUIDE_RU.md:
Russian user-facing command reference, arguments and practical workflows.

## Rule file ownership

Do not create duplicate development rule files.

Legacy development rules must be migrated into DEV_RULES.md.
