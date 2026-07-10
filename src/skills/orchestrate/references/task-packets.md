# Task packets

Use these compact contracts to keep delegation self-contained and synthesis
evidence-based. Remove fields that truly do not apply, but do not omit scope,
acceptance, verification, or limits.

## Goal contract

```text
Goal:
[the outcome to deliver]

Acceptance criteria:
- [observable requirement]

Source-of-truth context:
- [spec, repository rule, issue, file, or external contract]

Constraints and off-limits scope:
- [constraint or forbidden change]

Verification:
- [command, inspection, or evidence that proves completion]

Known dependencies:
- [ordering or shared-resource dependency]

Unresolved decisions:
- [decision that must stay with the orchestrator or advisor]
```

## Worker packet

```text
Workstream:
[stable identifier and short title]

Intent:
[why this workstream exists]

Expected output:
[patch, analysis, fixture, artifact, or decision input]

Owned scope:
- [files, directories, systems, or data this worker may change]

Inputs and completed dependencies:
- [artifact or decision already available]

Acceptance criteria:
- [worker-level observable requirement]

Verification:
- [focused command or evidence requirement]

Off-limits:
- [files, decisions, APIs, or adjacent cleanup not owned here]

Rules and skills:
- [relevant repository instructions or skill paths]

Return:
- artifacts or changed files
- verification evidence and exact result
- assumptions made
- unresolved limits or conflicts

Do not commit, widen scope, or modify unowned files unless explicitly
authorized. Do not present your own result as the final integrated sign-off.
```

## Worker result

```text
Workstream:
[identifier]

Status:
[complete | partial | blocked | failed]

Artifacts:
- [path, patch, result, or structured finding]

Acceptance evidence:
- [criterion]: [evidence]

Verification:
- [command or inspection]: [result]

Scope changes:
- [changed file or system]

Assumptions:
- [assumption]

Limits and conflicts:
- [missing evidence, dependency, overlap, timeout, or unexpected constraint]
```

## Final run report

```text
Outcome:
[the integrated deliverable]

Implementation owner:
[worker context | orchestrator context | mixed contexts]

Completed workstreams:
- [workstream]: [result]

Verification:
- [integration check]: [result]

Verification independence:
[independent context and identity | not independently verified]

Decisions and reconciliations:
- [material decision or conflict resolution]

Review:
- [independent review result, or why no review gate was needed]

Limits:
- [unverified behavior, failed lane, skipped scope, or remaining risk]

Next safe action:
[action, or "none"]
```

## Packet rules

- Prefer links or precise excerpts over dumping unrelated context.
- State observable acceptance criteria instead of asking a worker to "make it
  good."
- Assign one owner for every writable artifact.
- Supply completed dependency outputs before launching a dependent packet.
- Keep orchestration decisions out of worker scope.
- Require evidence in the result even when the worker reports success.
