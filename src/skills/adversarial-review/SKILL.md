---
name: adversarial-review
description: Run adversarial code review from fresh critic context. Use when the user asks for an adversarial review, hostile review, devil's advocate review, fresh-eyes review, critic agent review, or verification of agent-written code against a spec, diff, branch, or PR.
---

# Adversarial review

Use this skill to review code by separating the builder from the critic. The goal is not a second
ordinary code review. The goal is to force a cold-context reviewer to challenge whether the change
actually satisfies the user's intent, project contracts, and risk constraints.

## Critic routing at a glance

**Lead** means the model or models that produced the reviewed artifact — not merely the model handling
the current review request. A dynamic selector may use different concrete models across turns. Role
definitions and the runtime resolution procedure live under [Model routing](#model-routing).

| Lead                    | Quick/default critics                              | Ambiguous, high-risk, or deep critics              |
| ----------------------- | -------------------------------------------------- | -------------------------------------------------- |
| Cursor model            | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Quality GPT             | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Other GPT               | Quality GPT + (Quality Claude or Quality Cursor)   | Quality GPT + (Quality Claude or Quality Cursor)   |
| Claude / Anthropic      | Efficient GPT + Efficient Cursor                   | Quality GPT + Quality Cursor                       |
| GLM / Kimi family       | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Google / Gemini family  | Efficient GPT + (Quality Claude or Quality Cursor) | Efficient GPT + (Quality Claude or Quality Cursor) |
| Dynamic or unknown lead | Pinned cross-provider critics (dedicated rule)     | Pinned cross-provider critics (dedicated rule)     |
| Other                   | Efficient GPT + (Quality Claude or Quality Cursor) | Quality GPT + (Quality Claude or Quality Cursor)   |

`(A or B)` means prefer A when available; otherwise B. For a dynamic or unknown lead, resolve critics
via the dedicated rule under [Model routing](#model-routing) — do not infer a lead family from the
current chat model alone. For the visual flow and mode summary, see [README.md](README.md).

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
  table calls for it, and allow a distinct Cursor-pool model to review a Cursor lead when routing
  falls back to Quality Cursor. Label those lanes as partial independence; for GPT-on-GPT, also pair
  with a non-GPT critic.
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
     `skeptic`; do not substitute risk lanes. If Model routing allows only one credible critic,
     stay in `quick`, run that single skeptic, and record the missing lane under Review limits
     (see the Cursor-lead Quality Cursor collision exception).
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
   - Identify the lead (artifact builder model(s)), inspect the critic models the tooling actually
     exposes, and resolve the roles in [Model routing](#model-routing). In `quick`, assign the
     `skeptic` lens to both critics.
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
     Do not post rejected findings in the report. Post downgraded findings at their corrected
     severity — they remain lead-accepted.
   - Escalate findings supported by multiple lanes or by deterministic evidence.
   - If the spec is too vague to judge correctness, call that out as a spec gap instead of inventing a
     requirement.
   - Keep only lead-accepted findings for the posted report. Number them as `### N` under
     `## 📊 Findings` so developers can refer to specific entries (e.g. "apply 1 and 3" means Findings
     items 1 and 3).

6. **Post the written verdict report in the main chat.**
   Use [verdict-format.md](references/verdict-format.md).

   Strict sequence: **review → report → choices**.

   The written report is the primary review artifact. The parent/lead agent must post the full report
   as durable content in the main conversation before any remediation prompt. A report shown only in a
   critic subagent, tool panel, hidden transcript, or intermediate status is not sufficient. Do not
   replace, hide, summarize away, or substitute the report with remediation choices. Developers need
   the full `## 📊 Findings` and validation guidance to evaluate the choices.

   Put the complete report in the **body of your assistant message** — from `## 🎯 Verdict` through
   `## 📋 Review limits`, plus any optional sections defined in [verdict-format.md](references/verdict-format.md)
   (such as `## 🧭 Simpler alternative`), with every lead-accepted numbered finding. Do not include a
   lead-judgment section, rejected findings, or critic-only noise. Do not end a turn with only
   remediation choices and no report text.

7. **Offer remediation choice.**
   Skip this step when `## 📊 Findings` is empty.

   When findings exist:
   1. In the **same assistant turn** as step 6, write the full report in the message body first, then
      render inline remediation choices directly below it. Do not split report and choices across
      turns.
   2. Report text must precede the choices in the same message. If the user later says they cannot see
      the report, re-post the full report with inline choices in a new message.

   Fixed remediation choices — use these **base labels** in the inline prompt (no option ids, no
   counts):

   | Base label     |
   | -------------- |
   | Apply findings |
   | Do nothing     |

   When findings exist, always show both options. Append `(Recommended)` to **Apply findings**. Do not
   put counts in labels.

   **Fixed display order** — always list options as **Apply findings** → **Do nothing**.

   Inline format:

   ```markdown
   **How should I handle the review findings?**

   1. Apply findings (Recommended)
   2. Do nothing
   ```

   Keep the fixed prompt, base labels, display order, and `(Recommended)` suffix — never paraphrase,
   reorder, or add counts.

   Do not treat `## 🧭 Simpler alternative` as a finding unless it is also listed under
   `## 📊 Findings`.

   Treat user replies that match a base label (case-insensitive) as that choice. Treat a lone numeric
   reply (`1`, `2`, …) as selecting the option at that position in the numbered list shown above the
   prompt — not a Findings item position (that namespace applies only after the user chooses **Apply
   findings**).

   Follow-up per answer:
   - **Apply findings** — Implement every item under `## 📊 Findings`, using each finding's
     `Recommended fix` and `Validation` guidance. If the user names numbers (e.g. "1 and 3"), treat
     them as `### N` headings under `## 📊 Findings`. Then offer a focused adversarial re-review of
     the fix diff.
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
  (options where none is both cheaper and better).
- **Lead-only coding model** — a model family allowed as the builder/orchestrator but prohibited from
  critic lanes. GLM, Kimi, and Google/Gemini are lead-only families.

An eligible critic is exposed by the tooling, has a concrete reproducible model identity, is not an
exact known builder model of the reviewed artifact, satisfies the Fable gate, is not a lead-only
coding model, and remains usable under the benchmark-caveat policy below. Exclude routers,
`inherit`, and other dynamic model selections from every critic role — not only Efficient Cursor —
because they do not provide a reproducible critic identity.

Treat the lead as a **dynamic or unknown lead** when the artifact's builder identity is a dynamic
selector (Cursor Router/Auto is a recognition example for future agents), `inherit`, unresolved, or
otherwise not a known concrete model or set of concrete models that produced the work.

### Resolution procedure

1. Identify the lead: the model or models that produced the reviewed artifact — not merely the model
   handling this review request. Note provider and concrete model(s) when known. A dynamic selector
   may use different concrete models across turns.
2. If the lead is a dynamic or unknown lead, apply [Dynamic or unknown lead](#dynamic-or-unknown-lead)
   instead of pretending the underlying lead family is known from the current chat model.
3. Inspect the concrete model slugs the subagent tooling exposes. Do not invent or select unavailable
   models. Prefer pinned concrete critic identities over dynamic selections.
4. Resolve the table from known, current evidence. If the choice is unclear and web access is
   available, fetch the current official [Cursor evals](https://cursor.com/evals), intersect its
   entries with exposed models, consult the official
   [model and pricing documentation](https://cursor.com/docs/models-and-pricing), and calculate the
   roles above instead of guessing from remembered model names.
5. Treat CursorBench as evidence of agentic coding capability, not proof of reviewer-specific
   superiority. Do not automatically rank a contaminated or non-comparable score above an uncaveated
   candidate. Use a caveated model only when another reliable signal supports it or no credible
   uncaveated replacement exists, and record the reason under review limits. In particular, a
   caveated Cursor model cannot become Quality Cursor solely from that score.
6. If live evals or exact mappings are unavailable, resolve the generic roles from the exposed model
   catalog. Preserve the policy intent: capability for Quality roles, near-top value for Efficient
   GPT, cost efficiency for Efficient Cursor, and reliable capability for Quality Cursor.
7. If a preferred role cannot be filled, substitute without asking: avoid exact-model self-review
   against known builders, preserve the Fable and lead-only gates, prefer provider diversity, and
   disclose the heuristic substitution or reduced independence. When Quality Claude is unavailable,
   substitute Quality Cursor before other heuristics. If Quality Cursor resolves to a known concrete
   lead/builder model, use the next-best eligible Cursor first-party model; if none exists, skip that
   critic lane and record the limitation under Review limits. Run fewer lanes only when no credible
   replacement exists.

### Dynamic or unknown lead

When the lead is dynamic or unknown, do not route as if the underlying builder family were known.
Preserve the reviewer count and lenses chosen in workflow step 3. For `deep`, use up to that chosen
count only when pinned concrete critics from sufficiently distinct eligible provider families are
available; otherwise run fewer lanes and disclose the reduced coverage under Review limits.

1. Gather all known concrete builder models for the reviewed artifact and exclude them from critic
   selection.
2. If the selector's candidate pool is known, prefer pinned critics outside that pool.
3. If the candidate pool is known but contains or exhausts all eligible critic options, fall back to
   pinned cross-provider critics from different eligible provider families, label provenance as
   `limited independence`, and record a meaningful `## 📋 Review limits` item (for example that every
   eligible critic is inside the selector pool). Never claim exact-model independence that cannot be
   proven.
4. If the candidate pool or underlying builder identities are unknown, still pin critics from
   different eligible provider families — typically Efficient GPT + (Quality Claude or Quality
   Cursor) — but label provenance as `limited independence` and record `lead model identity unknown`
   (or an equivalent phrasing) as a meaningful `## 📋 Review limits` item. Never claim exact-model
   independence that cannot be proven.
5. If tooling reports the actual concrete model for a dynamic lead's current turn, exclude that model
   too, but do not assume it represents earlier builder turns.
6. Record the actual concrete critic model reported by tooling under **Reviewers**. If a configured
   critic was replaced or fell back and the actual model cannot be verified, disclose that under
   review limits.

### Routing constraints and provenance

- A Cursor lead routes to Efficient GPT + (Quality Claude or Quality Cursor). Keep this
  cost-conscious pairing even for deep reviews; apply deep-review lenses to these lanes instead of
  adding a third critic unless the user explicitly approves the extra cost. Exception: if Quality
  Claude is unavailable and Quality Cursor equals a known concrete lead/builder model, use the
  next-best eligible Cursor first-party model for that lane; if none exists, skip the second lane and
  continue with Efficient GPT alone. Stay in the chosen mode (`quick` included): do not invent a
  second critic. Record the lane shortfall under Review limits, emit a single-lane **Reviewers**
  line, and treat the missing lane as a meaningful review limit (`⚠️ PASS WITH RISKS` unless items
  under `## 📊 Findings` force `❌ FAIL`).
- A dynamic or unknown lead routes through the dedicated rule above, not through a guessed family row.
- Critic effort follows whatever the tooling or user already has configured for the selected model.
  Do not invent or force an effort level the tooling cannot set.
- GLM, Kimi, and Google/Gemini may appear as the lead but must never be selected as critics or
  substitutions. If no permitted critic is available, run fewer or no critic lanes and record the
  limitation; do not relax this gate.
- A distinct GPT reasoning model may review a GPT lead. Mark that lane as `partial independence`, pair
  it with a non-GPT critic whenever two lanes run, and never use an all-GPT committee.
- A distinct Cursor-pool model may review a Cursor lead. Mark that lane as `partial independence`,
  and also `heuristic substitution` when it replaced Quality Claude.
- When two `quick` skeptics run, they must not both be GPT models. A single-skeptic `quick` review
  from the collision exception above is allowed.
- Never select Fable as a critic unless the user explicitly requests it. Benchmark rank does not
  override this gate.
- Keep model names and versions out of the policy table. Under **Reviewers** in the verdict, record
  each resolved role and the concrete selected model the tooling actually reported, plus effort when
  known, and `partial independence`, `limited independence`, or heuristic-substitution notes when
  applicable. If a configured critic was replaced or fell back and the actual model cannot be
  verified, disclose that under review limits.

## Verdict standard

Emit one badge per report. See [verdict-format.md](references/verdict-format.md) for the full layout.

- **❌ FAIL** — at least one material correctness, security, data, spec, or regression issue should
  block. A `❌ FAIL` verdict must include at least one item under `## 📊 Findings`; if none qualify,
  use `⚠️ PASS WITH RISKS` or `✅ PASS` instead.
- **⚠️ PASS WITH RISKS** — no blocker, but there are meaningful non-blocking risks or missing
  validation.
- **✅ PASS** — no material issues found. Mention any review limitations.

When `## 📊 Findings` is empty, end after the verdict. When findings exist, run workflow step 7 before
making any code edits.
