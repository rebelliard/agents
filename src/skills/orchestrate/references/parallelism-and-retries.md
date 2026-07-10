# Parallelism and retries

Use parallel workers only when concurrency preserves ownership, causality, and
verification. More lanes are useful only when they shorten the critical path
without creating integration ambiguity.

## Decide whether work is parallel

Two packets may run concurrently when all of these are true:

- neither consumes unfinished output from the other;
- they do not write the same file, generated artifact, shared state, or public
  contract;
- each has independent acceptance criteria and a focused verification path;
- a failed lane can be isolated without invalidating the other's evidence;
- the orchestrator can integrate both results deterministically.

Keep packets sequential when they share:

- schema or migration ordering;
- API or type definitions that one packet must establish first;
- snapshots, lockfiles, generated indexes, or central registries;
- mutable external resources or environment state;
- product, architecture, security, or taste decisions still awaiting judgment.

When uncertain, make the dependency explicit and run the upstream packet first.

## Choose fan-out

There is no fixed worker count. Choose the smallest useful fan-out after
considering:

- width of the dependency graph;
- clean ownership boundaries;
- task hardness and executor availability;
- expected merge and verification cost;
- tool, token, latency, and user budget;
- risk of inconsistent assumptions;
- the orchestrator's ability to inspect every result.

Do not create workers solely to fill an available concurrency limit. Prefer one
well-scoped worker over several lanes that need continuous coordination.

## Write ownership

Assign one worker as the owner of each writable artifact. If several packets
need the same file:

1. designate one packet as the writer and make the others advisory;
2. sequence the packets around a stable intermediate contract; or
3. let workers return patches or recommendations for the orchestrator to apply
   centrally.

Never rely on concurrent workers to resolve overlapping edits themselves.

## Join behavior

Before advancing a dependent stage:

- account for every required lane as complete, partial, blocked, failed, or
  timed out;
- inspect artifacts rather than trusting status text;
- compare assumptions and contracts across lanes;
- identify integration work not owned by any packet;
- record missing evidence as a limit.

Independent successful lanes may be retained when another lane fails, but only
if their contracts and evidence remain valid without the failed output.

## Failure and retry routing

Diagnose a failed packet from its returned artifacts, verification evidence,
and changed repository state:

- repair missing context, constraints, or acceptance criteria before retrying;
- increase effort when the executor skipped available inspection or checks;
- increase capability when adequate context still produced wrong judgment;
- reduce scope or take over when safe delegation is no longer possible.

Before relaunching, update the packet with concrete failure evidence and changed
constraints. Keep retries bounded. Do not resend an unchanged prompt and expect
a different result.

## Cancellation and stale results

Cancel a lane when its output is no longer needed, its assumptions have been
invalidated, or an upstream decision changes its contract.

Mark results stale when they were produced against superseded files, schemas,
acceptance criteria, or dependency outputs. Revalidate a reusable artifact
against the current contract before integration.

## Verification limits

Report a limit when:

- a required lane did not complete;
- a worker could not run its focused check;
- integration verification is unavailable;
- overlapping ownership could not be resolved safely;
- external state changed during the run;
- the task depends on an unconfirmed assumption.

A limit may still permit a partial deliverable, but it must not be presented as
verified completion.
