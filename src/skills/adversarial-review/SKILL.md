---
name: adversarial-review
description: Run adversarial code review from fresh critic context. Use when the user asks for an adversarial review, hostile review, devil's advocate review, fresh-eyes review, critic agent review, or verification of agent-written code against a spec, diff, branch, or PR.
---

# Adversarial review

Use this skill to review code by separating the builder from the critic. The goal is not a second
ordinary code review. The goal is to force a cold-context reviewer to challenge whether the change
actually satisfies the user's intent, project contracts, and risk constraints.

## Critic routing at a glance

`Model running this chat` means the builder or orchestrator model in use when the user requests the
review. Role definitions and the runtime resolution procedure live under [Model routing](#model-routing).

| Model running this chat | Quick/default critics                              | Ambiguous, high-risk, or deep critics              |
| ----------------------- | -------------------------------------------------- | -------------------------------------------------- |
| Cursor model            | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Quality GPT             | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Other GPT               | Quality GPT + (Quality Claude or Quality Cursor)   | Quality GPT + (Quality Claude or Quality Cursor)   |
| Claude / Anthropic      | Efficient GPT + Efficient Cursor                   | Quality GPT + Quality Cursor                       |
| GLM / Kimi family       | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Google / Gemini family  | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Other                   | Efficient GPT + (Quality Claude or Quality Cursor) | Quality GPT + (Quality Claude or Quality Cursor)   |

`(A or B)` means prefer A when available; otherwise B. For the visual flow and mode summary, see
[README.md](README.md).

## Core rule

Do not let the same reasoning path that produced the code validate the code.

- Review only. Do not edit files unless the user chooses remediation in step 7 or explicitly asks for
  fixes later.
- Critics must receive review artifacts, not the builder's chat history or implementation rationale.
- Critics must not receive other critics' prompts, outputs, conclusions, or partial findings before the
  lead synthesis step.
- Prefer high-reasoning critics in genuinely separate reviewer contexts. See [Model routing](#model-routing)
  before spawning critics.
- Prefer provider diversity, but allow distinct GPT reasoning models to review each other when the
  table calls for it. Label that lane as partial independence and pair it with a non-GPT critic.
- Do not spend critic budget duplicating CI, hooks, formatters, or typechecks. Include those results
  only when already available or cheap; use critics for semantic issues deterministic checks miss.
- This skill complements always-on PR review automations; it is an opt-in review gate for agent output,
  large or risky diffs, ambiguous specs, and moments where fresh skeptical review is worth the latency.

## Workflow

1. **Define intent and scope.**
   - State what the change is supposed to accomplish.
   - Identify the review target: uncommitted changes, branch diff, PR diff, or named files.
   - Load source-of-truth contracts: user request, issue/spec, `AGENTS.md`/`CLAUDE.md`, tests, docs, and
     relevant reviewer rules.
   - When reviewing a branch or PR and a PR exists, load the PR title and body. Treat them as
     reviewer-facing claims about intent, scope, and validation to check against the code, not as
     unquestioned truth.
   - If the reviewed repository has `.github/pull_request_template.md`, load it as the expected PR body
     shape. Omitted template sections or `- N/A` are valid when they are genuinely not relevant.

2. **Create a critic packet.**
   Include only what a reviewer needs:
   - intent and explicit acceptance criteria
   - PR title and body, when available
   - PR template, when the reviewed repository defines one
   - diff or changed files
   - relevant specs/contracts
   - validation results already available or cheaply obtained
   - narrow surrounding context for changed code

   Exclude builder reasoning, excuses, implementation notes, and "why I chose this" context unless the
   user explicitly asks reviewers to evaluate tradeoffs. PR metadata is allowed because it is a durable
   reviewer-facing claim, not private builder rationale.

3. **Choose review mode and critic lanes.**
   Default to `quick`.
   - `quick`: two competing-model `skeptic` critics. Use for most changes. Keep both lanes as
     `skeptic`; do not substitute risk lanes.
   - `standard`: at most two critics. Use `skeptic` plus one risk-specific lane.
   - `deep`: at most three critics. Use only for large, high-risk, security-sensitive, or ambiguous
     changes where the added latency is justified.

   For `standard` and `deep` only, pick lanes by risk, using substitution before accumulation:
   - Design/system risk: add or substitute `architect`.
   - Regression/evidence risk: add or substitute `qa-risk`.
   - Security/auth/data-boundary risk: add or substitute `security`.
   - Over-engineering, unnecessary abstraction, or plausible simpler implementation risk: add or
     substitute `minimalist`.

   Lens definitions live in [reviewer-lenses.md](references/reviewer-lenses.md).

4. **Run critics independently.**
   - Identify the model running this chat, inspect the critic models the tooling actually exposes, and
     resolve the roles in [Model routing](#model-routing). In `quick`, assign the `skeptic` lens to both
     critics.
   - Launch critics in parallel when tooling allows it.
   - Give each critic the same critic packet plus its own lens instructions only. Do not include other
     critics' outputs or mention their conclusions until all critic lanes have finished or timed out.
   - Run them readonly.
   - Timebox each critic when the tool supports it. Record timeouts as review limits instead of waiting
     indefinitely.
   - Ask for findings only: no patches, no alternative implementation unless needed to explain a fix.
   - If a reviewer cannot run or returns empty output, record that under `## 📋 Review limits`, not in
     the verdict header.

   Use [reviewer-prompt.md](references/reviewer-prompt.md) as the critic prompt template and include the selected
   excerpt from [reviewer-lenses.md](references/reviewer-lenses.md) as the lens instructions.

5. **Synthesize as lead reviewer.**
   - Deduplicate overlapping findings.
   - Reject false positives, taste comments, and speculative risks that do not survive the evidence.
   - Escalate findings supported by multiple lanes or by deterministic evidence.
   - If the spec is too vague to judge correctness, call that out as a spec gap instead of inventing a
     requirement.
   - Record which findings land in **Accepted findings** vs rejected or downgraded. Number accepted
     items in a separate list (not the `### N` headings under `## 📊 Findings`) so step 7 can count them
     and developers can refer to specific entries (e.g. "apply 1 and 3" means accepted-list items 1
     and 3).

6. **Post the written verdict report in the main chat.**
   Use [verdict-format.md](references/verdict-format.md).

   Strict sequence: **review → report → choices**.

   The written report is the primary review artifact. The parent/lead agent must post the full report
   as durable content in the main conversation before any remediation prompt. A report shown only in a
   critic subagent, tool panel, hidden transcript, or intermediate status is not sufficient. Do not
   replace, hide, summarize away, or substitute the report with remediation choices. Developers need
   the full `## 📊 Findings`, `## ⚖️ Lead judgment`, and validation guidance to evaluate the choices.

   Put the complete report in the **body of your assistant message** — from `## 🎯 Verdict` through
   `## 📋 Review limits`, plus any optional sections defined in [verdict-format.md](references/verdict-format.md)
   (such as `## 🧭 Simpler alternative`), with every numbered finding and both lead-judgment lists. Do
   not end a turn with only remediation choices and no report text.

7. **Offer remediation choice.**
   Skip this step when `## 📊 Findings` is empty.

   When findings exist:
   1. Count `allFindings` (every numbered item under `## 📊 Findings`) and `acceptedFindings` (every
      numbered item under **Accepted findings** in `## ⚖️ Lead judgment`).
   2. In the **same assistant turn** as step 6, write the full report in the message body first, then
      render inline remediation choices directly below it. Do not split report and choices across
      turns.
   3. Report text must precede the choices in the same message. If the user later says they cannot see
      the report, re-post the full report with inline choices in a new message.

   Fixed remediation choices — use these **base labels** in the inline prompt (no option ids, no
   counts):

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

   Append `(Recommended)` to the **label text** of the lead-backed default option. Do not put counts
   in labels.

   **Fixed display order** — always list visible options in this order: **Apply accepted** → **Apply
   all** → **Do nothing**. Never reorder options based on which is recommended; only append
   `(Recommended)` to the default label.

   Example labels per scenario (omit hidden options; renumber contiguously from `1.`):
   - `accepted > 0`, `accepted === all`: `1.` Apply accepted (Recommended), `2.` Do nothing
   - `accepted > 0`, `accepted < all`: `1.` Apply accepted (Recommended), `2.` Apply all, `3.` Do
     nothing
   - `accepted === 0`, `all > 0`: `1.` Apply all, `2.` Do nothing (Recommended)

   Do not offer `Apply accepted` when `accepted.length === 0`. Do not treat `## 🧭 Simpler alternative` as
   a finding unless it is also listed under `## 📊 Findings`.

   Inline format:

   ```markdown
   **How should I handle the review findings?**

   1. Apply accepted (Recommended)
   2. Apply all
   3. Do nothing
   ```

   Use the same option visibility matrix. Omit hidden options and renumber the list contiguously from
   `1.` in the fixed display order above. Keep the fixed prompt, base labels, and `(Recommended)`
   suffix — never paraphrase, reorder, or add counts.

   Treat user replies that match a base label (case-insensitive) as that choice. Treat a lone numeric
   reply (`1`, `2`, `3`, …) as selecting the option at that position in the numbered list shown above
   the prompt — not an **Accepted findings** list position (that namespace applies only after the user
   chooses **Apply accepted**).

   Follow-up per answer:
   - **Apply accepted** — Implement only `acceptedFindings`, using each finding's `Recommended fix` and
     `Validation` guidance. If the user names numbers (e.g. "1 and 3"), treat them as **Accepted
     findings** list positions, not `### N` headings under `## 📊 Findings`. Then offer a focused
     adversarial re-review of the fix diff.
   - **Apply all** — Implement every item in `## 📊 Findings`, including lead-rejected or downgraded ones.
     Then offer re-review.
   - **Do nothing** — Make no code edits. End the skill run; verdict stands.

## Model routing

Resolve the roles in the top table at review time. Model availability in the current subagent tooling
is authoritative; a model appearing on a benchmark is not evidence that the user can select it.

### Roles

- **Quality GPT** — the highest-scoring eligible GPT model family exposed by the tooling, based on
  each family's best comparable benchmark configuration.
- **Efficient GPT** — the GPT model family whose best comparable configuration is the cheapest
  Pareto-efficient option (no alternative is both cheaper and better) within three CursorBench score
  points of Quality GPT. If exact score, cost, or slug mapping is unavailable, choose the cheaper
  near-top GPT family exposed by the tooling and disclose that heuristic. Critic effort follows
  whatever the tooling or user already has configured for that model.
- **Quality Claude** — the highest-scoring eligible Claude/Anthropic model exposed by the tooling.
  Exclude Fable unless the user explicitly requests it. If unavailable, substitute Quality Cursor
  before other heuristics and disclose the substitution. In the routing table this is written
  `(Quality Claude or Quality Cursor)`.
- **Quality Cursor** — the highest-scoring reliable eligible model in Cursor's first-party model pool.
  Preferred substitute when Quality Claude cannot be filled.
- **Efficient Cursor** — the cheapest eligible model on the Cursor first-party Pareto frontier
  (options where none is both cheaper and better). Exclude routers such as Auto because they do not
  provide a reproducible critic identity.
- **Lead-only coding model** — a model family allowed as the builder/orchestrator but prohibited from
  critic lanes. GLM, Kimi, and Google/Gemini are lead-only families.

An eligible critic is exposed by the tooling, is not the exact model running this chat, satisfies the
Fable gate, is not a lead-only coding model, and remains usable under the benchmark-caveat policy
below.

### Resolution procedure

1. Identify the provider and, when known, the concrete model running this chat.
2. Inspect the concrete model slugs the subagent tooling exposes. Do not invent or select unavailable
   models.
3. Resolve the table from known, current evidence. If the choice is unclear and web access is
   available, fetch the current official [Cursor evals](https://cursor.com/evals), intersect its
   entries with exposed models, consult the official
   [model and pricing documentation](https://cursor.com/docs/models-and-pricing), and calculate the
   roles above instead of guessing from remembered model names.
4. Treat CursorBench as evidence of agentic coding capability, not proof of reviewer-specific
   superiority. Do not automatically rank a contaminated or non-comparable score above an uncaveated
   candidate. Use a caveated model only when another reliable signal supports it or no credible
   uncaveated replacement exists, and record the reason under review limits. In particular, a
   caveated Cursor model cannot become Quality Cursor solely from that score.
5. If live evals or exact mappings are unavailable, resolve the generic roles from the exposed model
   catalog. Preserve the policy intent: capability for Quality roles, near-top value for Efficient
   GPT, cost efficiency for Efficient Cursor, and reliable capability for Quality Cursor.
6. If a preferred role cannot be filled, substitute without asking: avoid exact-model self-review,
   preserve the Fable and lead-only gates, prefer provider diversity, and disclose the heuristic
   substitution or reduced independence. When Quality Claude is unavailable, substitute Quality
   Cursor before other heuristics. Run fewer lanes only when no credible replacement exists.

### Routing constraints and provenance

- A Cursor lead always routes to exactly two critics: Efficient GPT + (Quality Claude or Quality
  Cursor). Keep this cost-conscious pairing even for deep reviews; apply deep-review lenses to these
  lanes instead of adding a third critic unless the user explicitly approves the extra cost.
- Critic effort follows whatever the tooling or user already has configured for the selected model.
  Do not invent or force an effort level the tooling cannot set.
- GLM, Kimi, and Google/Gemini may appear as the model running this chat but must never be selected
  as critics or substitutions. If no permitted critic is available, run fewer or no critic lanes and
  record the limitation; do not relax this gate.
- A distinct GPT reasoning model may review a GPT lead. Mark that lane as `partial independence`, pair
  it with a non-GPT critic whenever two lanes run, and never use an all-GPT committee.
- The two `quick` skeptics must not both be GPT models.
- Never select Fable as a critic unless the user explicitly requests it. Benchmark rank does not
  override this gate.
- Keep model names and versions out of the policy table. Under **Reviewers** in the verdict, record
  each resolved role and concrete selected model, plus effort when known, and partial-independence or
  heuristic-substitution notes when applicable.

## Verdict standard

Emit one badge per report. See [verdict-format.md](references/verdict-format.md) for the full layout.

- **❌ FAIL** — at least one material correctness, security, data, spec, or regression issue should
  block. A `❌ FAIL` verdict must include at least one item under **Accepted findings**; if none
  qualify, use `⚠️ PASS WITH RISKS` or `✅ PASS` instead.
- **⚠️ PASS WITH RISKS** — no blocker, but there are meaningful non-blocking risks or missing
  validation.
- **✅ PASS** — no material issues found. Mention any review limitations.

When `## 📊 Findings` is empty, end after the verdict. When findings exist, run workflow step 7 before
making any code edits.
