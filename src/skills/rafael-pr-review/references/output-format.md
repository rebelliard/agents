# Output format

Chat draft is the source of truth. GitHub posting uses the same
text after stripping the private footer.

## Full chat draft

````markdown
**PR Review** {header_emoji}

- 🔴 N High
- 🟡 N Medium
- 🟢 N Low
- 🔵 N Nit

{take_emoji} `[one or two sentences]`

<sub>Reviewed on: [{sha7}]({commit_url})</sub>

---

### Finding 1 — `path/to/file.ts`:42

🟡 **Medium** — `[title]`

- **Impact:** `[user- or system-visible consequence]`
- **Evidence:** `[blob link, symbol, or concrete proof]`
- **Suggested change:** `[smallest practical fix]`

<details>
<summary>✨ Suggested AI prompt</summary>

```text
On PR {pr_url}, fix {short problem}.
- Branch: `{branch}`

Problem:
- {bullet}
- {bullet}

Do:
1. {concrete step}
2. {concrete step}
3. Add/adjust tests: {what to assert}
4. Run scoped validation: {pnpm --filter … or equivalent}

💡 Keep the fix minimal. Do not expand scope.
```

</details>

### Finding 2 — `path/to/other.ts`:88

…

---

## For you (do not post)

🟢 **Approve** — `[short paragraph for Rafael only]`
````

Omit severity rows with count `0`. Omit findings sections when there
are none (clean review).

`header_emoji`: `📝` when posting findings; empty when clean.

Do **not** label the take (`Blunt take:`, `Summary:`, etc.). The
severity bullets already frame it. Lead the take line with
`{take_emoji}` only (see **Take emoji** below).

## Review summary body (GitHub `body`)

```markdown
**PR Review** {header_emoji}

- 🔴 N High
- 🟡 N Medium
- 🟢 N Low
- 🔵 N Nit

{take_emoji} `[one or two sentences]`

<sub>Reviewed on: [{sha7}]({commit_url})</sub>
```

When there are no findings and you still want a one-liner:

```markdown
**PR Review**

- No comments.

{take_emoji} `[optional one-liner]`

<sub>Reviewed on: [{sha7}]({commit_url})</sub>
```

When there are no findings and no one-liner, omit the take line and
keep the emoji on the bullet:

```markdown
**PR Review**

- No comments. 😊

<sub>Reviewed on: [{sha7}]({commit_url})</sub>
```

## Take emoji

Compute `{take_emoji}` from the signals below. First matching rule
wins. Do not invent other emojis. Do not use the private footer
(`🟢 Approve` / `🔴 Do not approve`) as a signal — that section is
chat-only and must not drive the posted take.

### Signals

| Signal              | How to compute                                                                         |
| ------------------- | -------------------------------------------------------------------------------------- |
| `high_count`        | Count of 🔴 High findings                                                              |
| `medium_count`      | Count of 🟡 Medium findings                                                            |
| `low_count`         | Count of 🟢 Low findings                                                               |
| `nit_count`         | Count of 🔵 Nit findings                                                               |
| `finding_count`     | `high_count + medium_count + low_count + nit_count`                                    |
| `unplaced_count`    | Findings folded under `### Unplaced findings`                                          |
| `commentable_count` | `finding_count - unplaced_count`                                                       |
| `smoke_fail`        | Smoke-QA appendix present **and** any **Tested** row Result does not start with `Pass` |
| `claim_fail`        | Metric/perf claim table present **and** any row Verdict is not a pass/confirmed match  |

`unplaced_count` and `commentable_count` do not pick an emoji on
their own — unplaced findings still count in the severity tallies.
Mention placement gaps in the take prose when relevant.

### Decision table (first match wins)

| #   | Condition                                    | Emoji | Meaning                                                 |
| --- | -------------------------------------------- | ----- | ------------------------------------------------------- |
| 1   | `high_count >= 1`                            | 🚨    | Blocking / correctness risk                             |
| 2   | `medium_count >= 3`                          | 🚧    | Several medium issues                                   |
| 3   | `medium_count >= 1`                          | ⚠️    | Needs attention; often shippable with follow-ups        |
| 4   | `low_count >= 3`                             | 🔧    | Several polish / guardrail items                        |
| 5   | `low_count >= 1`                             | 👍    | Light polish only                                       |
| 6   | `nit_count >= 1`                             | ✨    | Nits only                                               |
| 7   | `smoke_fail`                                 | 🧪    | Smoke/visual QA failed (no severity findings)           |
| 8   | `claim_fail`                                 | 📊    | Sold metrics/claims did not hold (no severity findings) |
| 9   | else (`finding_count == 0`, no fail signals) | 😊    | Clean                                                   |

Reserved elsewhere (never use as `{take_emoji}`):

- `📝` — `header_emoji` only when the review has findings
- `🟢` / `🔴` — private approve footer only

### Examples

| Counts / signals     | Take line                                              |
| -------------------- | ------------------------------------------------------ |
| H1                   | `🚨 Dual-write can clear state for existing clients.`  |
| M2                   | `⚠️ Two medium cache issues; ship after those land.`   |
| M3+                  | `🚧 Several medium gaps; I would not merge as-is.`     |
| L1, N2               | `👍 Small guardrail gap; nits optional.`               |
| L3+                  | `🔧 A handful of low-priority cleanups worth landing.` |
| N1 only              | `✨ Naming nit only.`                                  |
| clean                | `😊 Looks good — no comments.`                         |
| clean + `smoke_fail` | `🧪 Happy path passes; times-up dwell still flakes.`   |
| clean + `claim_fail` | `📊 Bundle claim does not match a fresh build.`        |

## Inline finding body (GitHub `comments[].body`)

Every finding **must** include the `✨ Suggested AI prompt` details
block. Use this label **verbatim** in `<summary>`.

````markdown
🟡 **Medium** — `[title]`

- **Impact:** `[…]`
- **Evidence:** `[…]`
- **Suggested change:** `[…]`

<details>
<summary>✨ Suggested AI prompt</summary>

```text
On PR {pr_url}, fix {short problem}.
- Branch: `{branch}`

Problem:
- {bullet}

Do:
1. {concrete step}
2. Add/adjust tests: {what to assert}
3. Run scoped validation: {command}

💡 Keep the fix minimal. Do not expand scope.
```

</details>
````

Severity line forms:

| Severity | Rendered opener           |
| -------- | ------------------------- |
| High     | `🔴 **High** — {title}`   |
| Medium   | `🟡 **Medium** — {title}` |
| Low      | `🟢 **Low** — {title}`    |
| Nit      | `🔵 **Nit** — {title}`    |

Leave a blank line after `</summary>` inside `<details>`.
Allowed HTML in posted bodies: `<details>`, `<summary>`, `<sub>`,
`<br />` only. Prefer GitHub blob links over external URLs.

## AI prompt content rules

The prompt inside the fence must be copy-pasteable for another agent:

1. Start with `On PR {pr_url}, {goal}.`, then put the head branch on
   its own bullet: `- Branch:` followed by the backticked branch name.
   Use capital `B`; never bury the branch in a parenthetical opener.
2. State the problem in short bullets with file/symbol cues.
3. Number concrete **Do** steps (fix + tests + scoped validation).
4. Close with `💡 Keep the fix minimal. Do not expand scope.`
5. Stay severity-proportional: Low/Nit prompts must not sound blocking.
6. Wrap code expressions in backticks, including identifiers,
   literals, expressions, commands, and repo-relative paths. When an
   expression already contains backticks, use `formatInlineCode()`
   rather than creating a broken single-backtick span.

## AI prompt preparation

Use
[`scripts/wrap-suggested-ai-prompt.ts`](../scripts/wrap-suggested-ai-prompt.ts)
to make prompt blocks deterministic. Prefer its `--build` mode with
the validated finding's `postPath`, `postLine`, `suggestedChange`, and
`evidence`; include `prUrl` and `headRef` when known:

From the skill root:

```bash
node scripts/wrap-suggested-ai-prompt.ts --build <<'EOF'
{
  "postPath": "{path}",
  "postLine": {line},
  "suggestedChange": "{suggested change}",
  "evidence": "{evidence}",
  "prUrl": "{pr_url}",
  "headRef": "{branch}"
}
EOF
```

Use the emitted `<details>…</details>` block unchanged. It applies the
`prepareSuggestedAiPromptText()` pipeline, which normalizes the opener
and branch, then soft-wraps at 80 columns. Numbered and bullet list
continuations receive a hanging indent equal to their marker width.
Blank lines and leading indentation remain intact; long URLs, paths,
and inline code spans stay unsplit.

For a custom body, assemble the inner text and pass it through the
script without `--build`. If constructing the block in TypeScript,
call `prepareSuggestedAiPromptText()` and select the outer fence with
`choosePromptBodyFence()` so an embedded triple-backtick run cannot
close the prompt early. Use `formatInlineCode()` for dynamic code
expressions, especially values that already contain backticks.

## Private footer (chat only)

Always end the chat draft with this section. Never include it in any
GitHub post.

```markdown
---

## For you (do not post)

🟢 **Approve** — `[why you would approve]`
```

or:

```markdown
---

## For you (do not post)

🔴 **Do not approve** — `[what blocks merge / what must change]`
```

Use exactly one of `🟢 **Approve**` or `🔴 **Do not approve**`.
One short paragraph. Address Rafael, not the PR author.

## Smoke QA appendix (optional)

Only when the user asks for visual / smoke / migration QA. Append
after findings (still before the private footer), using collapsible
sections:

```markdown
## Tested (pass)

<details>
<summary><strong>{Area}</strong> — {short scope}</summary>

| Route / flow | Tier   | Result        |
| ------------ | ------ | ------------- |
| `{route}`    | {tier} | Pass — {note} |

</details>

## Observations (not blockers)

| Item | Evidence | Verdict |
| ---- | -------- | ------- |
| …    | …        | …       |

## Not tested / couldn’t cover

| Area | Why |
| ---- | --- |
| …    | …   |
```

## Unplaceable findings

If a finding has no commentable diff line, put its full inline body
(including the AI prompt details) under the summary after the take
line, under a `### Unplaced findings` heading, and note that in chat
before posting. Unplaced findings still count toward severity tallies
and `{take_emoji}`.
