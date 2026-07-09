# Verdict format

Lead with findings. Keep summaries brief. Severity badges follow Pull Request Review conventions:
🔴 High, 🟡 Medium, 🟢 Low.

Under each numbered finding, put **What breaks**, **Why it matters**, **Recommended fix**, and
**Validation** in a sub-bullet list so nested fields are easier to scan.

Under `## 🎯 Verdict`, emit one bold badge and bullet metadata for **Intent reviewed** and
**Reviewers**. Do not include critic lane completion status in the verdict header; record failed,
empty, or timed-out lanes under `## 📋 Review limits`. For each critic, show its routing role and
concrete selected model and effort. Append `partial independence` or `heuristic substitution` when
applicable. For example: `Claude ([lead model]) → Efficient GPT ([selected model], [effort]) +
Efficient Cursor ([selected model], [effort])`, or for a deep review, `Claude ([lead model]) → Quality
GPT ([selected model], [effort]) + Quality Cursor ([selected model], [effort])`.

## Verdict badges

Emit exactly one badge per report (not all three):

| Verdict         | Rendered form          |
| --------------- | ---------------------- |
| FAIL            | **❌ FAIL**            |
| PASS WITH RISKS | **⚠️ PASS WITH RISKS** |
| PASS            | **✅ PASS**            |

Use bold + emoji, not inline code. Do not reuse severity emojis (🔴 🟡 🟢). In the report, render one
badge from the table above — do not pipe-join alternatives.

A **❌ FAIL** report must list at least one item under **Accepted findings**; otherwise use **⚠️ PASS
WITH RISKS** or **✅ PASS** (see **Verdict standard** in `SKILL.md`).

```markdown
## 🎯 Verdict

**❌ FAIL**

- **Intent reviewed:** `[one sentence]`
- **Reviewers:** `[lead model → role (concrete model, effort) + role (concrete model, effort), e.g. Composer → Efficient GPT ([selected model], medium) + Quality Claude ([selected model], high) | partial independence | heuristic substitution]`

## 📊 Findings

### 1. `[🔴 High | 🟡 Medium | 🟢 Low]` `[title]`

`[path or symbol]`

- **What breaks:** `[specific violated behavior, spec, or contract]`
- **Why it matters:** `[impact]`
- **Recommended fix:** `[smallest practical remediation]`
- **Validation:** `[test/check that should prove the fix]`

## ⚖️ Lead judgment

**Accepted findings:** (separate `1.`, `2.` list — not the `### N` headings under `## 📊 Findings`)

1. `[finding title]` - `[why it is real]`
2. `[finding title]` - `[why it is real]`

**Rejected or downgraded findings:**

- `[finding title]` - `[why it is false positive, speculative, or non-blocking]`

## 📋 Review limits

- `[missing spec, unavailable test run, huge diff slice, failed critic lane, or other residual risk]`
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
- **Reviewers:** `[lead model → role (concrete model, effort) + role (concrete model, effort), e.g. Composer → Efficient GPT ([selected model], medium) + Quality Claude ([selected model], high) | partial independence | heuristic substitution]`

No material issues found.

## 📋 Review limits

- None.
```

Pass with meaningful review limits:

```markdown
## 🎯 Verdict

**⚠️ PASS WITH RISKS**

- **Intent reviewed:** `[one sentence]`
- **Reviewers:** `[lead model → role (concrete model, effort) + role (concrete model, effort), e.g. Composer → Efficient GPT ([selected model], medium) + Quality Claude ([selected model], high) | partial independence | heuristic substitution]`

No material issues found.

## 📋 Review limits

- `[missing spec, unavailable test run, huge diff slice, failed critic lane, or other residual risk]`
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
- Inline choices use base labels only (`Apply accepted`, `Apply all`, `Do nothing`) in a numbered list
  (`1.`, `2.`, …) in fixed order: Apply accepted → Apply all → Do nothing (omit hidden options).
  The visibility matrix and inline format live in `SKILL.md` step 7 — do not paraphrase or partially
  copy them elsewhere.
- Remediation choices are contextual follow-up prompts, not a substitute for `## 📊 Findings`,
  `## ⚖️ Lead judgment`, or validation guidance.
- If the user cannot see the report, re-post the full report with inline choices in a new message.
- `## 📊 Findings` drives **Apply all** — every numbered finding, including lead-rejected or downgraded
  ones.
- `## 📊 Findings` uses `### N` headings; **Accepted findings** uses a separate numbered list. They are
  different namespaces — a finding can be `### 3` under `## 📊 Findings` and `2.` under **Accepted
  findings**.
- Numbered items under **Accepted findings** in `## ⚖️ Lead judgment` drive **Apply accepted** — only
  when non-empty. When a developer says "apply 1 and 3", those numbers refer to the **Accepted
  findings** list, not the `### N` headings under `## 📊 Findings`.
- Do not count `## 🧭 Simpler alternative` unless those items also appear under `## 📊 Findings`.
