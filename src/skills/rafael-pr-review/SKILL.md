---
name: rafael-pr-review
description: >-
  Draft Rafael-style GitHub PR reviews with severity semaphores,
  Impact/Evidence/Suggested change findings, and a mandatory
  ✨ Suggested AI prompt details block per finding. Outputs in chat
  by default; posts to GitHub only when asked. Ends with a private
  green/red approve note for Rafael. Use when reviewing a PR,
  writing a PR review, or posting a drafted review to GitHub.
disable-model-invocation: true
---

# Rafael PR review

Draft Rafael's human PR review for someone else's pull request. Chat
is the default deliverable. Post to GitHub only when asked.

This skill drafts Rafael's outbound human review. It does not replace
cold multi-critic gates for agent-written or high-risk changes, or
workflows that triage and address feedback already on a PR.

## Workflow

1. **Load the PR.** Title, body, head SHA, changed files, and the
   reviewable diff. Skim CI only when cheap or already visible. Treat
   the PR body as claims to check, not as truth.
2. **Review against heuristics.** Read
   [review-heuristics.md](references/review-heuristics.md). Prefer
   concrete defects over taste. Assign 🔴 High / 🟡 Medium / 🟢 Low /
   🔵 Nit.
3. **Draft the postable review in chat.** Follow
   [output-format.md](references/output-format.md) exactly:
   - Summary: `**PR Review**` + severity counts + blunt take +
     `Reviewed on` commit subline
   - One finding block per issue with **Impact**, **Evidence**,
     **Suggested change**
   - Every finding **must** include a collapsible
     `✨ Suggested AI prompt` details block (label verbatim)
   - Build each prompt block with
     [`scripts/wrap-suggested-ai-prompt.ts`](scripts/wrap-suggested-ai-prompt.ts)
     `--build` when possible; follow output-format.md for custom bodies
4. **Append the private footer.** After a `---` and
   `## For you (do not post)`, give Rafael exactly one of
   `🟢 **Approve**` or `🔴 **Do not approve**` plus a short paragraph.
   This section is for Rafael only. Never post it to GitHub.
5. **Stop unless asked to post.** Do not create a GitHub review,
   approve, or request changes unless the user asks.

## Output rules

- Templates and examples live in
  [output-format.md](references/output-format.md).
- Severity rows with count `0` are omitted.
- Clean reviews still show the summary (no findings) plus the private
  footer.
- Suggested AI prompts must be copy-pasteable: PR URL, problem
  bullets, numbered Do steps, scoped validation, keep-minimal.
- Suggested AI prompt bodies soft-wrap at 80 columns with hanging
  list indents. Use `- Branch:` with a backticked branch name, format
  code expressions as inline code, and choose a fence that cannot be
  closed by backticks inside the body.
- Prefer GitHub blob links with line numbers for evidence.
- Allowed HTML in posted bodies: `<details>`, `<summary>`, `<sub>`,
  `<br />` only.
- Optional smoke-QA appendix (details tables) only when the user asks
  for visual / smoke / migration QA.

## Posting to GitHub

Trigger phrases: "post it", "post to GH", "post that review", "submit
the review", or an explicit ask to post now when drafting.

When posting:

1. Strip `## For you (do not post)` and everything after it.
2. Apply any edits the user requested since the draft.
3. Post **one** atomic pull-request review:
   - `body` = summary block
   - `comments[]` = one inline comment per finding (`path`, `line`,
     finding body including the AI prompt details)
4. If a finding has no commentable diff line, fold its full body into
   the summary under `### Unplaced findings` and say so in chat.
5. Event defaults:
   - `COMMENT` unless the user asks otherwise
   - `REQUEST_CHANGES` only when the user explicitly asks
   - `APPROVE` only when the user explicitly asks (the private footer
     is advisory for Rafael, not an auto-approve)

Prefer `gh api` to create the review in one call (summary + inlines).
Verify the review landed. Paste the review URL in chat.

## Canonical skill tree

- `SKILL.md`
- `references/output-format.md`
- `references/review-heuristics.md`
- `scripts/wrap-suggested-ai-prompt.ts`

## Example trigger

User: "Review https://github.com/org/repo/pull/123"

Agent: drafts summary + findings (each with `✨ Suggested AI prompt`)
in chat, ends with private 🟢/🔴 note, does not post.

User later: "Post it"

Agent: strips private footer, posts atomic review, returns URL.
