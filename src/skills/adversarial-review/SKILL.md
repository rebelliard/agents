---
name: adversarial-review
description: Run adversarial code review from fresh critic context. Use when the user asks
  for an adversarial review, hostile review, devil's advocate review, fresh-eyes
  review, critic agent review, or verification of agent-written code against a
  spec, diff, branch, or PR.
---

# Adversarial review

Use this skill to review code by separating the builder from the critic. The
goal is not a second ordinary code review. The goal is to force a cold-context
reviewer to challenge whether the change actually satisfies the user's intent,
project contracts, and risk constraints.

For the visual flow and mode summary, see [README.md](README.md).

## Inputs

- **`review_target`** — Required. The artifact to review: uncommitted
  changes, branch diff, PR diff, named files, or supplied content.
- **`intent`** — Required when it is not already clear from the user request,
  issue, spec, or PR metadata. State what the change is supposed to accomplish
  before critics run.
- **`mode`** — Optional. One of `quick`, `standard`, or `deep`. Default to
  `quick` unless the user requests another mode or the size and risk guidance
  below justifies a heavier review.
- **`also_consider`** — Optional. Extra risks or contracts the user wants the
  critics to weigh alongside the normal adversarial review.

## Core rule

Do not let the same reasoning path that produced the code validate the code.

- Review only. Do not edit files unless the user chooses remediation in step 7
  or explicitly asks for fixes later.
- Critics must receive review artifacts, not the builder's chat history or
  implementation rationale.
- Critics must not receive other critics' prompts, outputs, conclusions, or
  partial findings before the lead synthesis step.
- Prefer high-reasoning critics in genuinely separate reviewer contexts. See
  [Model routing](#model-routing) before spawning critics.
- Prefer fewer independent critics over many same-family critics. If only one
  model family is available, run fewer lanes and label the result as limited
  independence.
- Do not spend critic budget duplicating CI, hooks, formatters, or typechecks.
  Include those results only when already available or cheap; use critics for
  semantic issues deterministic checks miss.
- This skill complements always-on PR review automations; it is an opt-in review
  gate for agent output, large or risky diffs, ambiguous specs, and moments
  where fresh skeptical review is worth the latency.

## Workflow

1. **Define intent and scope.**
   - State what the change is supposed to accomplish.
   - Identify the review target: uncommitted changes, branch diff, PR diff, or
     named files.
   - Record the requested `mode`, if provided. Record `also_consider` as extra
     review focus, not as a replacement for the core contracts.
   - Load source-of-truth contracts: user request, issue/spec,
     `AGENTS.md`/`CLAUDE.md`, tests, docs, and relevant reviewer rules.
   - When reviewing a branch or PR and a PR exists, load the PR title and body.
     Treat them as reviewer-facing claims about intent, scope, and validation to
     check against the code, not as unquestioned truth.
   - If the reviewed repository has `.github/pull_request_template.md`, load it
     as the expected PR body shape. Omitted template sections or `- N/A` are
     valid when they are genuinely not relevant.

2. **Create a critic packet.** Include only what a reviewer needs:
   - intent and explicit acceptance criteria
   - requested mode and `also_consider`, when provided
   - PR title and body, when available
   - PR template, when the reviewed repository defines one
   - diff or changed files
   - relevant specs/contracts
   - validation results already available or cheaply obtained
   - narrow surrounding context for changed code

   Exclude builder reasoning, excuses, implementation notes, and "why I chose
   this" context unless the user explicitly asks reviewers to evaluate
   tradeoffs. PR metadata is allowed because it is a durable reviewer-facing
   claim, not private builder rationale.

3. **Choose review mode and critic lanes.** Default to `quick`.

   Honor a user-provided `mode` unless the target clearly needs a heavier
   review; do not silently downgrade a requested mode. When no mode is provided,
   use size as a starting point, then adjust for risk. Count changed lines as
   added plus removed lines in the reviewed diff.

   | Mode       | Default reviewers                   | Use when                                                                                                                    |
   | ---------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
   | `quick`    | Two competing-model `skeptic`s      | Most changes where intent and contracts are clear; keep here for medium diffs only when risk stays low.                     |
   | `standard` | `skeptic` plus one risk lane        | Medium or risky changes: roughly 50-250 changed lines, 3-6 files, new user-visible behavior, or meaningful test gaps.       |
   | `deep`     | `skeptic` plus up to two risk lanes | Large changes: more than roughly 250 changed lines, more than 6 files, cross-module work, or multiple high-risk dimensions. |

   Keep `quick` reviewers as `skeptic`; do not substitute risk lanes. For
   small changes under roughly 50 changed lines and 1-2 files, a single
   independent `skeptic` is acceptable when review latency matters; record the
   reduced coverage under `## 📋 Review limits`.

   For `standard` and `deep`, always include `skeptic`, then pick risk lanes
   using substitution before accumulation. `standard` gets one risk lane; `deep`
   gets up to two risk lanes:
   - Design/system risk: add `architect`.
   - Regression/evidence risk: add `qa-risk`.
   - Security/auth/data-boundary risk: add `security`.
   - Over-engineering, unnecessary abstraction, or plausible simpler
     implementation risk: add `minimalist`.

   Lens definitions live in [reviewer-lenses.md](references/reviewer-lenses.md).

4. **Run critics independently.**
   - Identify the lead model family first, then pick the critic families from
     [Model routing](#model-routing). Use the reviewer count chosen in step 3:
     one independent critic for the small-change exception, two critics for
     normal `quick` and `standard` reviews, and up to three critics for `deep`.
     Use a third `deep` critic only when another genuinely independent context
     is available.
     Reduce that count when model routing cannot supply enough independent
     contexts; never exceed the available independent reviewers, and record the
     downgrade under `## 📋 Review limits`.
   - Assign lenses from step 3: every `quick` reviewer uses `skeptic`;
     `standard` uses `skeptic` plus the selected risk lane; `deep` uses
     `skeptic` plus the selected risk lanes. Use the highest reasoning tier
     available in each family when the tool supports model selection.
   - Launch critics in parallel when tooling allows it.
   - Give each critic the same critic packet plus its own lens instructions
     only. Do not include other critics' outputs or mention their conclusions
     until all critic lanes have finished or timed out.
   - Run them readonly.
   - Timebox each critic when the tool supports it. Record timeouts as review
     limits instead of waiting indefinitely.
   - Ask for findings only: no patches, no alternative implementation unless
     needed to explain a fix.
   - If a reviewer cannot run or returns empty output, record that under
     `## 📋 Review limits`, not in the verdict header.

   Use [reviewer-prompt.md](references/reviewer-prompt.md) as the critic prompt
   template and include the selected excerpt from
   [reviewer-lenses.md](references/reviewer-lenses.md) as the lens instructions.

5. **Synthesize as lead reviewer.**
   - Deduplicate overlapping findings.
   - Reject false positives, taste comments, and speculative risks that do not
     survive the evidence.
   - Escalate findings supported by multiple lanes or by deterministic evidence.
   - If the spec is too vague to judge correctness, call that out as a spec gap
     instead of inventing a requirement.
   - Record which findings land in **Accepted findings** vs rejected or
     downgraded. Number accepted items in a separate list (not the `### N`
     headings under `## 📊 Findings`) so step 7 can count them and developers
     can refer to specific entries (e.g. "apply 1 and 3" means accepted-list
     items 1 and 3).

6. **Post the written verdict report in the main chat.** Use
   [verdict-format.md](references/verdict-format.md).

   Strict sequence: **review → report → choices**.

   The written report is the primary review artifact. The parent/lead agent must
   post the full report as durable content in the main conversation before any
   remediation prompt. A report shown only in a critic subagent, tool panel,
   hidden transcript, or intermediate status is not sufficient. Do not replace,
   hide, summarize away, or substitute the report with remediation choices.
   Developers need the full `## 📊 Findings`, `## ⚖️ Lead judgment`, and
   validation guidance to evaluate the choices.

   Put the complete report in the **body of your assistant message** — from
   `## 🎯 Verdict` through `## 📋 Review limits`, plus any optional sections
   defined in [verdict-format.md](references/verdict-format.md) (such as
   `## 🧭 Simpler alternative`), with every numbered finding and both
   lead-judgment lists. Do not end a turn with only remediation choices and no
   report text.

7. **Offer remediation choice.** Skip this step when `## 📊 Findings` is empty.

   When findings exist:
   1. Count `allFindings` (every numbered item under `## 📊 Findings`) and
      `acceptedFindings` (every numbered item under **Accepted findings** in
      `## ⚖️ Lead judgment`).
   2. In the **same assistant turn** as step 6, write the full report in the
      message body first, then render inline remediation choices directly below
      it. Do not split report and choices across turns.
   3. Report text must precede the choices in the same message. If the user
      later says they cannot see the report, re-post the full report with inline
      choices in a new message.

   Fixed remediation choices — use these **base labels** in the inline prompt
   (no option ids, no counts):

   | Base label     |
   | -------------- |
   | Apply accepted |
   | Apply all      |
   | Do nothing     |

   Option visibility:

   | `accepted` | `all`         | Apply accepted | Apply all | Do nothing | Default        |
   | ---------- | ------------- | -------------- | --------- | ---------- | -------------- |
   | 0          | 0             | — (skip step)  | —         | —          | —              |
   | N          | N (N > 0)     | Yes            | No        | Yes        | Apply accepted |
   | 0          | M (M > 0)     | No             | Yes       | Yes        | Do nothing     |
   | K          | M (0 < K < M) | Yes            | Yes       | Yes        | Apply accepted |

   Append `(Recommended)` to the **label text** of the lead-backed default
   option. Do not put counts in labels.

   **Fixed display order** — always list visible options in this order: **Apply
   accepted** → **Apply all** → **Do nothing**. Never reorder options based on
   which is recommended; only append `(Recommended)` to the default label.

   Example labels per scenario (omit hidden options; renumber contiguously from
   `1.`):
   - `accepted > 0`, `accepted === all`: `1.` Apply accepted (Recommended), `2.`
     Do nothing
   - `accepted > 0`, `accepted < all`: `1.` Apply accepted (Recommended), `2.`
     Apply all, `3.` Do nothing
   - `accepted === 0`, `all > 0`: `1.` Apply all, `2.` Do nothing (Recommended)

   Do not offer `Apply accepted` when `accepted.length === 0`. Do not treat
   `## 🧭 Simpler alternative` as a finding unless it is also listed under
   `## 📊 Findings`.

   Inline format:

   ```markdown
   **How should I handle the review findings?**

   1. Apply accepted (Recommended)
   2. Apply all
   3. Do nothing
   ```

   Use the same option visibility matrix. Omit hidden options and renumber the
   list contiguously from `1.` in the fixed display order above. Keep the fixed
   prompt, base labels, and `(Recommended)` suffix — never paraphrase, reorder,
   or add counts.

   Treat user replies that match a base label (case-insensitive) as that choice.
   Treat a lone numeric reply (`1`, `2`, `3`, …) as selecting the option at that
   position in the numbered list shown above the prompt — not an **Accepted
   findings** list position (that namespace applies only after the user chooses
   **Apply accepted**).

   Follow-up per answer:
   - **Apply accepted** — Implement only `acceptedFindings`, using each
     finding's `Recommended fix` and `Validation` guidance. If the user names
     numbers (e.g. "1 and 3"), treat them as **Accepted findings** list
     positions, not `### N` headings under `## 📊 Findings`. Then offer a
     focused adversarial re-review of the fix diff.
   - **Apply all** — Implement every item in `## 📊 Findings`, including
     lead-rejected or downgraded ones. Then offer re-review.
   - **Do nothing** — Make no code edits. End the skill run; verdict stands.

## Model routing

Before spawning critics, identify the **lead model family** for this session —
the model running the builder or orchestrator that invoked this skill (for
example Composer, GPT, Opus, or another Claude/Anthropic model).

Prefer critics from **non-lead** model families so the review is not just the
same reasoning path restated in a new prompt. In Cursor, use this default
routing table:

| Lead model family | Default critic families |
| ----------------- | ----------------------- |
| Composer          | GPT + Opus              |
| GPT               | Opus + Composer         |
| Opus or Claude    | GPT + Composer          |

In Cursor, these defaults mean:

- **Composer lead → GPT + Opus critics.** Do not use Composer as a default
  critic.
- **GPT lead → Opus + Composer critics.** Do not use GPT as a default critic.
- **Opus or other Claude/Anthropic lead → GPT + Composer critics.** Do not use
  any Claude/Anthropic model as a default critic.
- Do not hardcode model version strings in prompts or skill docs; families are
  enough.
- Record the lead family and critic families in the verdict under **Reviewers**.
- If one default critic family is unavailable, run the remaining lane, note
  limited independence under **Reviewers** (e.g.
  `Composer → GPT | limited independence`), and record the gap in review limits.

Portable fallback:

- Outside Cursor or when these exact families are unavailable, choose the most
  independent readonly reviewer contexts available. Prefer another model family
  first, then another provider, then a separate high-reasoning context from the
  same family as a last resort.
- If no independent critic context is available, run one readonly critic in the
  best available context, do not claim cross-model review, and record
  `limited independence` plus the routing constraint under **Review limits**.

## Verdict standard

Emit one badge per report. See [verdict-format.md](references/verdict-format.md)
for the full layout.

- **❌ FAIL** — at least one material correctness, security, data, spec, or
  regression issue should block. A `❌ FAIL` verdict must include at least one
  item under **Accepted findings**; if none qualify, use `⚠️ PASS WITH RISKS` or
  `✅ PASS` instead.
- **⚠️ PASS WITH RISKS** — no blocker, but there are meaningful non-blocking
  risks or missing validation.
- **✅ PASS** — no material issues found. Mention any review limitations.

When `## 📊 Findings` is empty, end after the verdict. When findings exist, run
workflow step 7 before making any code edits.
