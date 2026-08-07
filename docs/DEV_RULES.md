# Development Rules

This file contains persistent instructions for AI agents working on this project.

Every future patch MUST follow these rules.

## Documentation requirements

1. Any patch that changes architecture, project structure, completed features, current focus or next steps MUST update docs/PROJECT_STATE.md.
2. PROJECT_STATE.md synchronization is a mandatory development step, not an optional documentation task.
3. The documentation synchronization rule must remain in PROJECT_STATE.md after every update.

## Project state requirements

1. The Current focus section must describe the actual development stage.
2. The Next steps section is written primarily for the next AI agent, not for human readers.
3. Next steps must contain enough technical context to continue development without guessing:
   - current architectural assumptions;
   - files or systems involved;
   - known limitations;
   - migration risks;
   - expected implementation direction.
4. Avoid vague instructions like "continue development" or "add features".

## Patch quality rules

1. Inspect the current project state before creating a patch.
2. Do not assume previous architecture if the current snapshot differs.
3. Prefer small verified changes over large speculative rewrites.
4. Every patch must include validation commands.
5. Tests must represent the intended architecture, not a temporary incorrect assumption.
6. Preserve backwards compatibility unless migration is explicitly planned.

## Architecture rules

1. Keep responsibilities separated.
2. Avoid adding new systems when existing systems can be connected.
3. Before introducing a new abstraction, check whether it belongs to an existing domain object.
4. When temporary architecture exists, document migration requirements.

## AI continuation rules

Future AI agents should treat this file and PROJECT_STATE.md as the source of truth for project continuation.
