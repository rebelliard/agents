# Review heuristics

Recurring threads from Rafael's PR reviews. Prefer these over generic
reviewer checklists. Severity definitions align with Mentimeter agents
PR review (High / Medium / Low / Nit).

## Tone and evidence

- Be blunt and conclusion-first. Lead with the defect, not throat-clearing.
- Prefer concrete evidence: blob links, symbols, measured claims, repro
  steps. Do not post taste comments as findings.
- Keep severity-proportional tone. Low and Nit must not read as blockers.
- When the PR sells numbers (bundle size, Lighthouse, class counts),
  independently re-measure before trusting the description.

## Severity quick map

- **🔴 High** — correctness, security, data loss, broken contracts,
  silent production footguns (e.g. deploy dual-write that clears state
  for everyone).
- **🟡 Medium** — real impact that should fix soon: attribution bugs,
  cache-key coincidences, missing tests for non-trivial behavior,
  a11y/focus regressions, overclaimed "no behavior change".
- **🟢 Low** — simplification, docs drift, narrow guardrails, optional
  hardening.
- **🔵 Nit** — style, wording, cosmetic preferences.

## Patterns you actually catch

Look for these when the diff touches related surfaces:

- **Overclaimed parity** — PR says no behavior change but edge cases
  diverge (empty collections, non-interactive modes, legacy paths).
- **Cache-key coincidence** — readers and writers use differently named
  helpers that only match today via a shared deprecated key.
- **Deploy / dual-write footguns** — publishing legacy fields that old
  clients can clear or corrupt for new clients.
- **Attribution vs layout coupling** — UI props reused for analytics
  surfaces (e.g. `placement` hiding QR while also selecting
  `signupSurface`).
- **Focus / keyboard / dwell races** — enter-exit focus, times-up dwell
  treating pause/cancel as elapsed, late joiners adopting stale wire
  state.
- **Test gaps** — non-trivial behavior covered only by mocks that hide
  the failure mode (wholesale SWR mocks, fixture size without
  correctness).
- **Scope vs enforcement** — docs or root agent rules claim a broad
  policy while the linter/test only covers a subset.

## What not to raise

- CI/format/typecheck noise already visible on the PR unless you have
  a semantic point CI misses.
- Speculative "could someday" risks without a concrete path in this
  diff.
- Drive-by refactors unrelated to the PR intent.

## Special modes

- **Visual / smoke / migration QA** — use the smoke-QA appendix in
  [output-format.md](output-format.md). Evidence tables and screenshots
  beat vague "looks fine".
- **Metric / perf claim PRs** — verify claims in a short table
  (claim → independent measurement → verdict) before or instead of
  nitpicking implementation taste.
- **Approve with follow-ups** — Medium/Low findings can ship with a
  clear take line (`⚠️` / `👍` per output-format.md); put the
  personal approve call in the private footer, not as a fake clean
  pass.
