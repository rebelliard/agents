---
name: pr-stack-planner
description: >-
  Analyzes large pull requests, branches, or diffs and proposes reviewable
  independent or stacked PR strategies with self-contained green slices,
  ownership and dependency boundaries, GitHub-comment-ready handoff plans, and
  optional Markdown export. Use when deciding whether a large change should be
  split, designing a dependent PR stack, or preparing a stack plan for another
  agent to execute.
---

# PR stack planner

Analyze and propose the split. Do not create branches, rewrite commits, push, or
open PRs unless the user separately asks for execution.

## Workflow

1. **Load the change.**
   - For a GitHub PR, inspect title, body, base/head, commits, changed files,
     checks, and review state with `gh`.
   - Read linked tickets or specs when they define intent.
   - Read repository instructions and ownership signals such as `CODEOWNERS`.
   - For local work, compare committed and uncommitted changes with the default
     branch.
2. **Map the work.**
   - Separate contracts, file moves, behavior changes, consumers, cleanup,
     tests, generated files, package metadata, and documentation.
   - Identify ownership boundaries, central risk points, and real dependencies.
   - Distinguish mechanical volume from semantic risk.
3. **Choose the strategy.**
   - Prefer independent PRs from the default branch when slices do not depend on
     each other.
   - Use a stack only for real compile-time, runtime, migration, or compatibility
     dependencies.
   - Recommend keeping one PR when splitting would duplicate scaffolding,
     prolong two architectures, or make intermediate states misleading.
4. **Design self-contained slices.**
   - Each PR must compile and pass required checks against its declared base.
   - A PR must not depend on a later PR to fix tests, types, exports, or runtime
     behavior.
   - Keep tests, dependencies, lockfiles, configuration, generated output, and
     ownership updates with the change that needs them.
   - Use the smallest temporary compatibility bridge needed for a green
     intermediate state.
5. **Challenge the plan.**
   - Check whether each boundary is understandable to its likely reviewers.
   - Check merge and rollback order.
   - Check that file moves remain reviewable as moves where possible.
   - Predict conflicts, invalid intermediate states, and missing validation.
6. **Deliver a handoff plan.**
   - Lead with a human TL;DR.
   - Give the recommendation and ordered slices.
   - Explain why the boundaries work and which alternatives to avoid.
   - Record evidence, unknowns, validation, and execution constraints.

## Slice contract

For every proposed PR, specify:

- proposed conventional title, preserving any trailing-emoji rule supplied by
  the user or repository;
- outcome and reviewer-sized scope;
- base branch or predecessor;
- included changes and explicit exclusions;
- ownership or likely reviewer boundary;
- compatibility or migration state after merge;
- scoped validation and required CI;
- material risk or behavior that deserves focused review.

Do not split by arbitrary file counts, directories, or repeated domain entities
when every slice would cross the same seam. Split by deliverable, ownership,
risk, and verification boundaries.

## Existing history and conflict guidance

Treat commits as evidence, not automatic PR boundaries. Look for fixups,
temporary scaffolding, accidental truncations, conflict-repair commits, and
later commits that make earlier checkpoints buildable.

When the plan will be executed later, include these defaults:

1. Snapshot the original head.
2. Rebase a temporary copy onto the latest default branch before slicing.
3. Resolve shared conflicts once on that copy.
4. Keep the original remote branch unchanged.
5. Reconstruct clean slices from the rebased result.
6. Compare the final stack with the original intended diff using `range-diff`
   and path-level comparisons.

## Front-load questions

Predict questions that could stop execution: access, authorship, branch naming,
ownership, ambiguous behavior, validation availability, or incompatible
intermediate states.

Resolve them from source evidence and safe defaults. Ask at most one consolidated
set of questions, with recommended answers, only when the answers materially
change the stack or final behavior. Otherwise state assumptions and continue.

## Execution-model guidance

When the handoff environment offers Sol and Grok:

- use Sol for strategy, architecture decisions, per-slice review, and the final
  cross-stack audit;
- use Grok for mechanical rebase, hunk movement, branch operations, validation,
  GitHub updates, and advice on execution sequencing;
- keep one writer per worktree or branch.

Resolve actual model names from the available tooling. Do not invent slugs or
make the plan fail when either model is unavailable.

## Default output: GitHub comment draft

Return a post-ready GitHub comment in chat by default. Do not post it unless the
user explicitly asks.

Use this shape, omitting sections that have no useful content:

```markdown
## TL;DR

<What the change does, whether to split it, and the proposed merge direction.>

## Proposed stack

| #   | Proposed PR            | Base   | Purpose                  |
| --- | ---------------------- | ------ | ------------------------ |
| 1/N | `<conventional title>` | `main` | <self-contained outcome> |
| 2/N | `<conventional title>` | PR 1   | <self-contained outcome> |

## Why these boundaries

- <Ownership, risk, move-only, compatibility, or verification reason.>

## Execution notes

- <Rebase, reconstruction, ordering, and one-writer constraints.>

## Validation

- <Checks each slice must pass independently.>

## Questions and unknowns

- <Only material unresolved items.>
```

If asked to post, use GitHub tooling, verify the comment landed, and return its
URL.

## PR-body stack table

When PR URLs exist or the user asks for PR-body instructions, include the same
full stack table in every PR body:

- add `Depends on`, `Blocks`, and `Stack order: N/M` when useful;
- use three columns: `#`, `PR`, `Role`;
- for every non-current row, put the PR link in the `PR` column
  (`[#N](URL)`);
- for the current row, put exactly `📍 this PR` in the `PR` column — never a
  numbered link, and never `_(this PR)_` / `*(this PR)*` in the `Role` column;
- move that current-row marker when writing each PR body.

### Role text

Derive `Role` from the PR title:

1. Strip the conventional-commit prefix (`type(scope):`, `type!:`, `type:`,
   including optional scope and breaking-change `!`).
2. Keep the remainder verbatim, including any trailing title emoji.
3. Format it in sentence case (capitalize the first letter; leave package names,
   paths, and symbols as they appear in the title).
4. Prefer backticks around package names, paths, and symbols when the title uses
   them or when they would otherwise read as plain prose.

Do not invent shorter role summaries. The role should read as the title without
the conventional-commit prefix.

Title emoji policy comes from rules outside this skill:

- If the exact PR title has a trailing emoji, copy that exact emoji after the
  role in the body table.
- If the PR title has no trailing emoji, do not add one to the table.
- Never invent, remove, or replace a title emoji.
- The `📍 this PR` marker lives only in the `PR` column and is independent of
  the title emoji.

Example:

```markdown
| #   | PR          | Role                            |
| --- | ----------- | ------------------------------- |
| 1/2 | 📍 this PR  | Introduce explicit contracts 😇 |
| 2/2 | [#102](URL) | Remove the compatibility bridge |
```

## Optional Markdown export

When the user asks for a file, write the same handoff plan to their requested
path. If no path is supplied, use
`stack-plan-for-<PR_NUMBER>.md` at the repository root. Follow that repository's
Markdown formatting and validation rules.

## Quality bar

- The recommendation is supported by inspected files, commits, ownership, and
  dependencies.
- The plan says when not to split.
- Every proposed PR is self-contained and independently green.
- The first section is useful to humans who will not read the full analysis.
- Unknowns and assumptions are explicit.
- The output is a plan another agent can execute without rediscovering the
  architecture.
