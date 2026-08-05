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

Blunt take: `[one or two sentences]`

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

Keep the fix minimal. Do not expand scope.
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

## Review summary body (GitHub `body`)

```markdown
**PR Review** {header_emoji}

- 🔴 N High
- 🟡 N Medium
- 🟢 N Low
- 🔵 N Nit

Blunt take: `[one or two sentences]`

<sub>Reviewed on: [{sha7}]({commit_url})</sub>
```

When there are no findings:

```markdown
**PR Review**

- No comments. 😊

Blunt take: `[optional one-liner]`

<sub>Reviewed on: [{sha7}]({commit_url})</sub>
```

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

Keep the fix minimal. Do not expand scope.
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
4. Say keep the fix minimal / do not expand scope.
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
(including the AI prompt details) under the summary after the blunt
take, under a `### Unplaced findings` heading, and note that in chat
before posting.
