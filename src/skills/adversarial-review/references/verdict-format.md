# Verdict format

Lead with findings. Keep summaries brief. Severity badges follow Pull Request Review conventions:
🔴 High, 🟡 Medium, 🟢 Low.

Under each numbered finding, put **What breaks**, **Why it matters**, **Recommended fix**, and
**Validation** in a sub-bullet list so nested fields are easier to scan.

`## 📊 Findings` lists only lead-accepted findings. Reject false positives, taste comments, and
speculative risks during synthesis; do not post them. Post downgraded findings at their corrected
severity — they remain lead-accepted. There is no separate lead-judgment section.

Under `## 🎯 Verdict`, emit one bold badge and bullet metadata for **Intent reviewed** and
**Reviewers**. Do not include critic lane completion status in the verdict header; record failed,
empty, or timed-out lanes under `## 📋 Review limits`. For each critic, show its routing role and the
concrete selected model the tooling actually reported, plus effort when known. Append
`partial independence`, `limited independence`, or `heuristic substitution` when applicable. For
example:
`Claude ([lead model]) → Efficient GPT ([selected model]) + Efficient Cursor ([selected model])`, or
for a deep review,
`Claude ([lead model]) → Quality GPT ([selected model]) + Quality Cursor ([selected model])`. For a
Cursor-led review:
`Composer ([lead model]) → Efficient GPT ([selected model]) + Quality Claude ([selected model])`, or
when Quality Claude cannot be filled by a distinct Cursor-pool model,
`Composer ([lead model]) → Efficient GPT ([selected model]) + Quality Cursor ([selected model]) | partial independence | heuristic substitution`.
For a dynamic or unknown lead when underlying builders cannot be proven:
`Dynamic lead (underlying models unknown) → Efficient GPT ([selected model]) + Quality Claude ([selected model]) | limited independence`
(and record `lead model identity unknown`, or equivalent, under Review limits). When Quality Claude
is unavailable and Quality Cursor equals a known concrete lead/builder model, use the next-best
eligible Cursor first-party model; if none exists, omit the second lane (e.g.
`Composer ([lead model]) → Efficient GPT ([selected model])`), record the shortfall under Review
limits, and treat that missing lane as a meaningful review limit. If a configured critic was replaced
or fell back and the actual model cannot be verified, disclose that under Review limits.

## Verdict badges

Emit exactly one badge per report (not all three):

| Verdict         | Rendered form          |
| --------------- | ---------------------- |
| FAIL            | **❌ FAIL**            |
| PASS WITH RISKS | **⚠️ PASS WITH RISKS** |
| PASS            | **✅ PASS**            |

Use bold + emoji, not inline code. Do not reuse severity emojis (🔴 🟡 🟢). In the report, render one
badge from the table above — do not pipe-join alternatives.

A **❌ FAIL** report must list at least one item under `## 📊 Findings`; otherwise use **⚠️ PASS WITH
RISKS** or **✅ PASS** (see **Verdict standard** in `SKILL.md`).

```markdown
## 🎯 Verdict

**❌ FAIL**

- **Intent reviewed:** `[one sentence]`
- **Reviewers:** `[lead model → role (concrete model[, effort]) + role (concrete model[, effort]), e.g. Composer → Efficient GPT ([selected model]) + Quality Claude ([selected model]), Composer → Efficient GPT ([selected model]) + Quality Cursor ([selected model]) | partial independence | heuristic substitution, or Dynamic lead (underlying models unknown) → Efficient GPT ([selected model]) + Quality Claude ([selected model]) | limited independence]`

## 📊 Findings

### 1. `[🔴 High | 🟡 Medium | 🟢 Low]` `[title]`

`[path or symbol]`

- **What breaks:** `[specific violated behavior, spec, or contract]`
- **Why it matters:** `[impact]`
- **Recommended fix:** `[smallest practical remediation]`
- **Validation:** `[test/check that should prove the fix]`

## 📋 Review limits

- `[missing spec, unavailable test run, huge diff slice, failed critic lane, lead model identity unknown, unverified critic fallback, or other residual risk]`
```

If there are no findings, say so plainly but still show review provenance. Pick the badge from the
table above:

- **✅ PASS** — no material issues and no meaningful review limits (or only trivial limits).
- **⚠️ PASS WITH RISKS** — no material issues, but review limits are meaningful enough that the user
  should not treat the result as a clean pass.

Clean pass (no meaningful limits):

```markdown
## 🎯 Verdict

**✅ PASS**

- **Intent reviewed:** `[one sentence]`
- **Reviewers:** `[lead model → role (concrete model[, effort]) + role (concrete model[, effort]), e.g. Composer → Efficient GPT ([selected model]) + Quality Claude ([selected model]), Composer → Efficient GPT ([selected model]) + Quality Cursor ([selected model]) | partial independence | heuristic substitution, or Dynamic lead (underlying models unknown) → Efficient GPT ([selected model]) + Quality Claude ([selected model]) | limited independence]`

No material issues found.

## 📋 Review limits

- None.
```

Pass with meaningful review limits:

```markdown
## 🎯 Verdict

**⚠️ PASS WITH RISKS**

- **Intent reviewed:** `[one sentence]`
- **Reviewers:** `[lead model → role (concrete model[, effort]) + role (concrete model[, effort]), e.g. Composer → Efficient GPT ([selected model]) + Quality Claude ([selected model]), Composer → Efficient GPT ([selected model]) + Quality Cursor ([selected model]) | partial independence | heuristic substitution, or Dynamic lead (underlying models unknown) → Efficient GPT ([selected model]) + Quality Claude ([selected model]) | limited independence]`

No material issues found.

## 📋 Review limits

- `[missing spec, unavailable test run, huge diff slice, failed critic lane, lead model identity unknown, unverified critic fallback, or other residual risk]`
```

Optional advisory section when the `minimalist` lane ran and found a simpler alternative without a
blocking issue:

```markdown
## 🧭 Simpler alternative

**Over-engineering: [🟢 Low | 🟡 Medium | 🔴 High]**

- `[bullet summarizing current approach vs simpler alternative]`
```

## Remediation sets

After the verdict, workflow steps 6–7 in `SKILL.md` use these sets to build remediation choices:

- The strict sequence is **review → report → choices**.
- The parent/lead agent must post the written verdict report in the main conversation. A report shown
  only in a critic subagent, tool panel, hidden transcript, or intermediate status is not sufficient.
- Put the full report in the **assistant message body** first; then render numbered inline remediation
  choices in the **same turn** when findings exist. Never offer choices in a turn that omits the report
  text.
- Inline choices use base labels only (`Apply findings`, `Do nothing`) in a numbered list (`1.`,
  `2.`) in fixed order: Apply findings → Do nothing. The inline format lives in `SKILL.md` step 7 —
  do not paraphrase or partially copy it elsewhere.
- Remediation choices are contextual follow-up prompts, not a substitute for `## 📊 Findings` or
  validation guidance.
- If the user cannot see the report, re-post the full report with inline choices in a new message.
- Numbered `### N` items under `## 📊 Findings` are lead-accepted only and drive **Apply findings**.
  When a developer says "apply 1 and 3", those numbers refer to the `### N` headings under
  `## 📊 Findings`.
- Do not count `## 🧭 Simpler alternative` unless those items also appear under `## 📊 Findings`.
