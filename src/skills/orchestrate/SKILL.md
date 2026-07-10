---
name: orchestrate
description: Orchestrate ambitious, multi-workstream coding-agent goals through
  scoped delegation, adaptive parallel execution, central verification, and
  final synthesis. Use when a task needs several independent workers, coordinated
  research and implementation, dependency-aware fan-out, or an end-to-end
  deliverable that one linear agent run is unlikely to complete reliably.
---

# Orchestrate

Use this skill to turn a complex goal into a verified deliverable without
turning the workflow into an unbounded committee. This skill owns the
orchestration loop, role boundaries, runtime role selection, recovery, and
independent review gate. Keep the policy version-free so available models can
change without changing this skill.

## Orchestration at a glance

| 🎯 Situation                                 | 🧭 Route                                                         |
| -------------------------------------------- | ---------------------------------------------------------------- |
| Small or sequential task                     | Execute directly; do not orchestrate                             |
| Several independent, verifiable workstreams  | Build a task graph and use adaptive parallel workers             |
| Workstreams share files or unfinished APIs   | Assign one writer or sequence them                               |
| Consequential ambiguity or architecture      | Consult a read-only advisor before implementation                |
| Worker skipped context or verification       | Repair the packet or raise effort, then retry within a bound     |
| Adequate context still produced bad judgment | Raise executor capability                                        |
| Integrated result is large or high-risk      | Verify deterministically, then run independent read-only critics |

## Practical scope

Use this skill when the main request is **coordinate and deliver an entire
multi-workstream project**. It owns decomposition, dependency ordering, worker
packets, parallel execution, integration, and final verification—not merely the
choice of model or effort for one task.

Example one-line prompts:

- "Coordinate the feature, migration, docs, and end-to-end verification."
- "Split this cross-cutting change into safe parallel workstreams and deliver
  the integrated result."
- "Run the independent investigations, reconcile their conclusions, and
  implement the verified fix."
- "Take this ambitious goal from plan through delegated execution to one final
  deliverable."

## Boundaries

Keep four roles distinct:

- **Orchestrator** — owns the goal contract, task graph, arbitration, central
  verification, and final synthesis.
- **Worker** — executes one scoped, verifiable packet. A worker may edit only
  within its assigned scope and cannot sign off on its own result.
- **Advisor** — provides read-only judgment at a consequential decision point.
  Use only when ambiguity, architecture, risk, or taste justifies the latency.
- **Critic** — performs optional cold-context review after implementation.
  Keep this context independent from the workers and their rationale.

Resolve roles from models the current tooling actually exposes. Availability is
authoritative: do not invent a model slug or assume plan, region, or provider
access. Choose by task fit and verification needs, with cost as a tie-breaker.

## When not to orchestrate

Execute directly when the task is small, sequential, or cheaper to complete
than to describe as several worker packets. Do not fan out merely because
subagents are available.

Use this loop when at least one condition holds:

- the deliverable contains independent research or implementation workstreams;
- separate repository areas can be owned and verified independently;
- parallel investigation materially reduces time to a decision;
- the task is long-running enough that explicit checkpoints and synthesis
  reduce the chance of an incomplete result.

## Workflow

### 1. Establish the goal contract

Before delegation, state:

- the concrete deliverable;
- acceptance criteria and source-of-truth constraints;
- relevant files, systems, and repository rules;
- what is off-limits;
- deterministic verification and any unavoidable judgment checks;
- known dependencies, risks, and unresolved decisions.

Use the goal contract in
[task-packets.md](references/task-packets.md). Repair missing context before
changing model capability or adding workers.

### 2. Route capability and advice

Classify each proposed workstream independently:

- clear, mechanical, and strongly verifiable work uses an efficient executor;
- normal implementation uses a balanced executor;
- subtle, ambiguous, unfamiliar, or judgment-heavy work uses a stronger
  executor;
- architecture, risk, or "what are we missing?" questions may use a read-only
  advisor before implementation.

Use higher effort when a capable executor needs more inspection, persistence,
or verification. Use higher capability when adequate context still produces
wrong judgment. Repair missing context, tools, acceptance criteria, or
verification paths before changing either. A single orchestration run may use
different capability and effort for different packets.

Use an advisor only at a consequential decision point. Prefer a capable,
independent context when available, keep it read-only, and convert accepted
advice into the goal contract, worker constraints, and verification plan. The
advisor does not become an executor.

### 3. Build the task graph

Split work by deliverable and verification boundary, not by arbitrary file
count. Mark dependencies explicitly.

Run packets in parallel only when they can proceed without depending on one
another's unfinished output. Avoid concurrent write ownership of the same file,
generated artifact, migration sequence, shared state, or public contract.

Derive fan-out from the task graph, ownership boundaries, risk, verification
cost, budget, and available tooling. There is no fixed worker count. Read
[parallelism-and-retries.md](references/parallelism-and-retries.md) before
launching workers.

### 4. Send self-contained worker packets

Each worker receives only the context needed for its task:

- intent and expected output;
- owned files or systems;
- dependencies and supplied inputs;
- acceptance criteria;
- verification commands or evidence requirements;
- off-limits scope;
- repository rules and relevant skills;
- instruction not to commit or expand scope unless explicitly authorized.

Use the worker packet in
[task-packets.md](references/task-packets.md). A worker must report artifacts,
evidence, changed scope, and limits—not only a narrative summary.

### 5. Join and inspect

Wait for every required dependency lane to finish, fail, or time out before
synthesizing that stage.

Inspect returned artifacts directly. Check for:

- contract satisfaction;
- conflicting assumptions between workers;
- overlapping or out-of-scope edits;
- invented APIs or missing dependencies;
- verification evidence that does not prove the claimed behavior;
- integration work that no packet owned.

Treat failed, empty, or timed-out lanes as orchestration limits. Do not disguise
missing work as successful synthesis.

### 6. Verify centrally

The orchestrator runs or requests the checks that prove the integrated
deliverable. A worker transcript is not evidence, and worker-local checks do
not replace integration checks.

When a packet fails, diagnose the evidence before retrying:

- repair context or acceptance criteria when the packet was underspecified;
- raise effort when the executor skipped obtainable evidence or checks;
- raise capability when adequate context still produced wrong judgment;
- take over or reduce scope when the work cannot be delegated safely.

Make retries targeted and bounded. Do not resend an unchanged packet.

If the orchestrator takes over implementation, final verification must come
from an independent context or the run report must mark the result as not
independently verified.

### 7. Apply the optional review gate

After deterministic verification, run an independent review when the user asks
for fresh eyes or when the integrated result is large, ambiguous,
security-sensitive, or otherwise worth a semantic challenge.

Give read-only critics intent, contracts, the integrated diff or artifacts, and
validation results. Exclude builder rationale and isolate critics from one
another until synthesis. Deduplicate findings, reject unsupported suggestions,
apply only evidence-backed fixes, and revalidate changed behavior.

### 8. Synthesize the deliverable

Return one coherent result, not a bundle of worker messages. Use the final run
report in [task-packets.md](references/task-packets.md) and include:

- delivered outcome;
- workstreams completed;
- verification performed and results;
- material decisions or reconciled conflicts;
- unresolved limits and skipped work;
- the next safe action, when one remains.

## Invariants

- The orchestrator owns final judgment and verification.
- Workers never validate their own work as the final gate.
- Any orchestrator-authored implementation needs independent final verification
  or an explicit verification limit.
- Parallel work has explicit ownership and dependency boundaries.
- Capability and effort choices are resolved from current availability and task
  evidence, never permanent model names.
- Independent critics do not receive worker rationale or each other's findings
  before synthesis.
- Missing evidence is reported as a limit, not inferred as success.
- Fan-out remains adaptive; worker count is never a permanent policy constant.
