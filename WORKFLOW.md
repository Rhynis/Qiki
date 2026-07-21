# Collaboration Workflow

This repo is built by two AI assistants working together, coordinated by the human owner.

## Roles

| Role | Who | Responsibility |
| --- | --- | --- |
| **Planner / Reviewer** | Claude | Reads `gasbot_build_plan.md`, writes issues with refined scope + acceptance criteria, reviews PRs, requests changes. Does NOT write feature code. |
| **Implementer** | Codex | Reads the issue, implements the code on a feature branch, opens a PR, addresses review comments. |
| **Owner** | Human | Relays messages when needed, gives final approval, merges PRs, manages secrets. |

## Per-phase flow

1. **Planning (Claude)**
   - Open a GitHub issue using the `Phase Task` template.
   - Fill in scope, out-of-scope, acceptance criteria, and architectural notes from `gasbot_build_plan.md`.
   - Assign branch name: `phase-X.Y-<short-name>`.

2. **Implementation (Codex)**
   - Create the branch from `main`: `git checkout -b phase-X.Y-<short-name>`.
   - Implement the listed deliverables. Do NOT add anything outside the scope.
   - Run the verification commands locally before pushing.
   - Push and open a PR using the PR template. Link the issue with `Closes #N`.

3. **Review (Claude)**
   - Read the PR diff and verification output.
   - Check each acceptance-criteria box against the actual code.
   - Either approve, or leave change requests as PR comments. Comments must be specific (file + line + what to change + why).

4. **Iteration (Codex)**
   - Push fixes to the same branch.
   - Reply to each review comment with the commit SHA that addresses it.

5. **Merge (Owner)**
   - Final read-through.
   - Merge the PR. Delete the branch.
   - Move on to the next phase.

## Ground rules

- **One phase, one branch, one PR.** No mixing phases.
- **No silent scope creep.** If implementation reveals something missing from the issue, comment on the issue first, get it added to scope, then implement.
- **Verification commands must actually run.** Pasting expected output is not acceptable; paste real terminal output.
- **The build plan is the source of truth** for what to build. The issue is the source of truth for the current task's scope.
- **English in code, comments, and PR text. Vietnamese only in user-facing UI strings.**

## Communication artifacts

| Artifact | Purpose |
| --- | --- |
| GitHub Issue | Task definition (scope, criteria, notes) |
| GitHub PR | Implementation + review thread |
| `gasbot_build_plan.md` | Long-term reference (gitignored from the repo, lives only on the owner's machine) |
| `BUILD_PLAN_FOUNDATION.md` | Reusable, project-agnostic template for build plans, workflow, code-quality standards, issue/prompt templates, and CI/CD — copy into future projects (gitignored, owner's machine only) |
| This file | Process documentation |
