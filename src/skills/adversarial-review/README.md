# Adversarial review skill

## Overview

Runs an opt-in cold-context review for agent-written or high-risk changes.

Use it when a change needs a separate critic to challenge intent fit, contracts, edge cases, and risk
before human review or merge.

It helps the agent:

- Spawn isolated critics with focused review lenses.
- Focus review effort on semantic risks rather than rerunning CI or formatters.
- Return a clear verdict: fail, pass with risks, or pass.

## When to use it

Use this skill when a normal review is not enough because the same agent or
model family produced the work being judged. It is especially useful for:

- Agent-written code that needs fresh skepticism before human review.
- Large diffs, cross-module changes, or changes with unclear ownership.
- Security, permissions, data-boundary, payment, or user-data changes.
- PRs whose title or body make claims that should be checked against the diff.
- Ambiguous specs where reviewers should call out gaps instead of inventing
  requirements.

Do not use it as a slower replacement for formatters, typechecks, or ordinary
CI. Include those results when they are already available, but spend critic
budget on semantic risk.

## Inputs

- `review_target`: required. Uncommitted changes, branch diff, PR diff, named
  files, or supplied content.
- `intent`: required when it is not already clear. State what the change is
  supposed to accomplish before running critics.
- `mode`: optional. One of `quick`, `standard`, or `deep`. The workflow honors
  a requested mode unless the target clearly needs a heavier review.
- `also_consider`: optional. Extra risks, contracts, or review focus from the
  user.

## Review modes

| Mode       | Review shape                        | Best fit                                                                                                                    |
| ---------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `quick`    | Default: two independent `skeptic`s | Most changes where intent and contracts are clear; keep here for medium diffs only when risk stays low.                     |
| `standard` | `skeptic` plus one risk lane        | Medium or risky changes: roughly 50-250 changed lines, 3-6 files, new user-visible behavior, or meaningful test gaps.       |
| `deep`     | `skeptic` plus up to two risk lanes | Large changes: more than roughly 250 changed lines, more than 6 files, cross-module work, or multiple high-risk dimensions. |

Count changed lines as added plus removed lines in the reviewed diff. For very
small changes under roughly 50 changed lines and 1-2 files, a single
independent `skeptic` is acceptable when latency matters. Record that reduced
coverage in the review limits.

## Reviewer lanes

The skill includes focused lenses in `references/reviewer-lenses.md`:

- `skeptic`: challenges whether the implementation satisfies intent.
- `architect`: checks fit with the surrounding system.
- `qa-risk`: hunts regression paths and missing evidence.
- `security`: reviews trust boundaries, secrets, permissions, and data risk.
- `minimalist`: challenges unnecessary scope and complexity.

`quick` keeps all critics in the `skeptic` lane. `standard` uses `skeptic` plus
one risk lane. `deep` uses `skeptic` plus up to two risk lanes.

## Output

The lead reviewer synthesizes the independent critics into one durable report:

- `## 🎯 Verdict` with exactly one bold badge: **❌ FAIL**, **⚠️ PASS WITH
  RISKS**, or **✅ PASS**.
- `## 📊 Findings` with a severity badge, path or symbol evidence, and the
  fields **What breaks**, **Why it matters**, **Recommended fix**, and
  **Validation**.
- `## ⚖️ Lead judgment` separating accepted findings from false positives or
  downgraded issues.
- `## 📋 Review limits` for missing context, failed critic lanes, or limited
  model independence.

When findings exist, the skill offers remediation choices after the full report:
apply accepted findings, apply all findings, or do nothing.

The report must be posted as durable main-chat content before remediation
choices. Keep the strict order: review, then report, then choices.

## Files

- `SKILL.md`: operational workflow and model-routing rules.
- `references/reviewer-prompt.md`: critic prompt template.
- `references/reviewer-lenses.md`: lane definitions.
- `references/verdict-format.md`: report format and remediation rules.
