# Reviewer lenses

Use only the lanes that fit the change. Each lane should stay in its lane and avoid duplicating generic
review advice.

## Skeptic

Primary job: prove the implementation does not satisfy the stated intent.

Look for:

- missing requirements
- violated acceptance criteria
- incorrect assumptions about inputs, states, or order of operations
- edge cases that change observable behavior
- tests that pass while failing to assert the important behavior
- meaningful drift between PR title/body and the diff, such as unsupported claims, important
  undisclosed behavior, or scope framing that would mislead a reviewer

## Architect

Primary job: challenge whether the design fits the surrounding system.

Look for:

- broken ownership boundaries
- abstractions that make the system harder to change
- duplicated logic that should use an established local pattern
- data flow, lifecycle, or concurrency mistakes
- changes that solve the local problem while damaging adjacent modules

## QA risk

Primary job: find regression paths and missing evidence.

Look for:

- untested user-visible behavior
- important negative cases
- state transitions, retries, cancellation, and partial failure paths
- fixture gaps where tests exercise mocks instead of the risky contract
- places where a deterministic check should exist instead of model judgment

## Security

Primary job: find boundary violations.

Use for auth, permissions, secrets, payments, user data, external input, network calls, storage, and
cross-tenant behavior.

Look for:

- auth bypasses and confused-deputy flows
- privilege escalation or missing ownership checks
- injection, unsafe deserialization, XSS, SSRF, path traversal, and command execution
- secret/PII leakage in logs, prompts, telemetry, errors, or persisted records
- dependency and supply-chain risks introduced by the change

## Minimalist

Primary job: challenge scope and complexity by asking whether a simpler solution genuinely exists.

Look for:

- speculative features
- compatibility shims for unshipped branch work
- broad refactors not required by the intent
- new abstractions that hide simple behavior
- formatting churn or unrelated edits that make the PR harder to review

Output an advisory over-engineering verdict: 🟢 `Low`, 🟡 `Medium`, or 🔴 `High`.

- 🟢 `Low`: current approach is reasonably simple; do not invent an alternative.
- 🟡 `Medium`: a simpler approach likely exists, but the current approach is still understandable.
- 🔴 `High`: the implementation appears materially more complex than needed.

When verdict is `Medium` or `High`, describe the simpler alternative in 2-4 bullets. Do not block on
minimalism alone; only escalate to a blocking finding when the complexity creates a concrete
correctness, maintainability, or review-trust problem.
