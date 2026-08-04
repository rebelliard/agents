---
name: pr-review-comments
description: Triage and address GitHub pull request feedback — formal review threads and human conversation comments that function as reviews (for example Ellinor/esvalberg top-level PR comments). Decide which suggestions are worth acting on, make focused fixes, commit and push accepted changes, then reply by default. Prefix non-Aikido replies with taxonomy emojis (👍🏽 😇 🆗 📌 🔜 ❓). Aikido `@AikidoSec` replies must start with `@AikidoSec` and must not use any emoji prefix. In GitHub replies, link named code symbols to remote blob URLs with line numbers. Never post GitHub replies about uncommitted or unpushed work — commit and push first, then reply with a verified commit link. On very high-reasoning hosts, delegate mechanical fetch/fix/post work to a Grok subagent. Use when the user provides a PR link and asks to review comments, address review feedback, respond inline, resolve threads, or decide which comments are worth acting on. Only skip posting GitHub replies when the user explicitly asks not to post, comment, or reply.
---

# PR Review Comments

## Goal

When the user provides a GitHub PR link and asks to review or address feedback:

1. Read every relevant piece of review feedback, not only formal inline review threads.
2. Decide whether each comment should be acted on, dismissed, or clarified with the user.
3. Make focused code changes for comments worth acting on, but only when the user asked to act.
4. Validate, commit, and push accepted code changes.
5. Reply to each addressed comment by default, unless the user explicitly asks not to post anything.
6. Resolve completed formal review threads by default after replying, unless the user explicitly asks not to resolve threads.

Match the user's requested code-change scope. If they only ask for a review or assessment, do not edit files, but still post concise replies and resolve completed formal threads unless they explicitly asked not to post anything. Treat "just review the comments," "handle the PR comments," "triage the feedback," and similar phrasing as permission to post replies.

When the user asks to address or handle comments and you agree a comment needs a change, implement and validate the focused fix before replying to or resolving that thread. Do not merely say that you agree or intend to make the change.

## Precedence / companion skills

Apply constraints from companion skills when available. **Missing companions must not fail execution** — if a path cannot be loaded, continue with the inlined extracts below and note the gap in the chat summary only when relevant.

| Skill                  | Applies to                                  | Inlined extract                                                                                                                                                                        |
| ---------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rafael-writing-style` | GitHub replies and chat completion summary  | Conclusion-first; concise; STE; anti-AI cleanup (no sycophancy, filler, "I hope this helps"); commits as linked short SHA (not inline code); never invent certainty or blocker framing |
| `karpathy-guidelines`  | Triage + code changes for acted-on comments | Surface ambiguity / ask; minimum fix; no speculative abstractions; surgical edits only for the comment under reply; verify before claiming Fixed                                       |
| `deslop`               | Diffs introduced while addressing comments  | No drive-by comments, defensive try/catch, or `any` casts; prefer early returns over deeper nesting; keep behavior unchanged unless the review finding requires a fix                  |

**Precedence when they conflict:**

1. Safety / "never post about unpushed work" and verified commit links (this skill)
2. User's explicit ask for this run (plan-first, don't resolve, only triage, etc.)
3. Repo / OpenSpec / stack contract for what belongs in this PR
4. Karpathy surgical scope + deslop for the code change
5. Rafael writing-style for reply prose (inside the fixed openers / link formats this skill defines)

Blob+line links for named symbols are required by this skill even when writing-style allows plain backticks.

Typical paths (non-fatal if absent):

- `~/.claude/skills/rafael-writing-style/SKILL.md` or `~/.cursor/skills/rafael-writing-style/SKILL.md`
- repo `.claude/skills/karpathy-guidelines/SKILL.md` when working in <repo>
- cursor-team-kit `deslop` skill when available

## Execution routing (token efficiency)

If this skill is running on a **very high-reasoning / expensive host model**, delegate bulk mechanical work to a **Grok subagent** (Cursor Task tool; model family `cursor-grok` / latest available Grok slug). Keep judgment on the host.

**Delegate to Grok (mechanical, high-token):**

- Fetching PR metadata, review threads, conversation comments
- Resolving blob SHAs / line numbers for symbol links
- Drafting first-pass reply text from the taxonomy
- Applying surgical code fixes, running scoped validation, commit/push plumbing
- Posting replies / resolving threads after decisions are settled

**Keep on the high-reasoning host (judgment):**

- Act / dismiss / ask decisions on ambiguous or product-scope comments
- Stack / OpenSpec handoff calls
- Final reply wording when the user asked plan-first or the thread is sensitive
- Whether to ignore vs fix Aikido findings

When plan-first: parent reviews the triage table and exact replies before GitHub mutation. Otherwise Grok may execute within this skill's safety rules. Goal: token efficiency while staying smart.

If Grok is unavailable, run everything on the host — do not fail the skill.

## What Counts As Review Feedback

Treat all of the following as in-scope review feedback:

1. **Formal inline review threads** from `reviewThreads` (path/line-anchored comments).
2. **Formal review summaries** on submitted reviews (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`) when the body contains actionable feedback.
3. **PR conversation comments** (issue comments on the pull request) from humans when they function as a review — for example findings, requested changes, bug reports, design pushback, or "should fix" notes left in the Conversation tab instead of via "Submit review".

Do **not** skip conversation comments just because they are not GitHub "review" objects. Some reviewers (for example Ellinor / `esvalberg`) regularly leave real review feedback as top-level PR comments.

Ignore conversation noise unless the user asks for everything:

- Bots and automation in the **Conversation** tab: `linear`, `vercel`, `github-actions`, `cursor`, `copilot*`, Aikido, Dependabot, and similar
- Deploy/preview notices, Vercel access errors, Happo/CI status dumps with no human ask
- Empty approval bodies with no feedback text

**Exception — formal Aikido review threads:** ignore Aikido only as conversation-tab noise. Unresolved formal inline threads from `aikido-pr-checks` are in-scope review feedback. Triage them and use the `@AikidoSec` directives below when you reply.

When unsure whether a human conversation comment is review feedback, include it and triage it.

## Writing Style

Use ASD-STE100 Simplified Technical English principles for GitHub replies and the completion summary:

- Use common, precise words. Avoid uncommon or academic words when a plain alternative has the same meaning. For example, write "the fallback always returned an empty array" instead of "the fallback was vacuous."
- Use active voice.
- Write short sentences. Put one main point in each sentence.
- Use one topic in each paragraph. Use a list when it makes complex information easier to read.
- Name the code, behavior, or result directly. Do not use vague references.
- Keep established software terms and code identifiers when they make the message more precise.
- Treat STE as a clarity guide, not as a strict vocabulary check. Do not change or weaken the technical meaning to follow it.

Anti-slop for replies: no praise padding, no chatbot preambles, no stacked hedging. Evidence over vibes. Conclusion-first.

### Reply taxonomy (emoji prefixes)

**Non-Aikido replies** start with a **single emoji prefix** then **exactly one space**.

| Prefix | When                                                                                                       | Typical opener after the emoji                          |
| ------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 👍🏽     | Fix committed and pushed (or suggested change applied). Always this medium skin tone — never ✅ or bare 👍 | `Fixed in [shortsha](…): …` / `Applied the suggested …` |
| 😇     | No code change; leaving as-is                                                                              | `Leaving this as-is because …`                          |
| 🆗     | Tip already has the fix                                                                                    | `Already handled/covered on the current branch. …`      |
| 📌     | Valid polish, not done in this PR                                                                          | `Accepted for this slice. …`                            |
| 🔜     | Deferred to a later stack / OpenSpec PR                                                                    | `Keeping … for this PR only.` / handoff to `#N`         |
| ❓     | Need reviewer/user input                                                                                   | Short clarifying question                               |

**Aikido replies (hard rule):** the reply body **must start with** `@AikidoSec` — **no emoji before it**, including not 🛡️ or 📡. Any leading character before `@AikidoSec` breaks Aikido's trigger parsing.

| Directive              | When                                                                          | Body shape                                                                    |
| ---------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `@AikidoSec feedback:` | Finding is real but diagnosis/severity/remedy should improve for future scans | `@AikidoSec feedback: <general rule>` then optional blank line + `Fixed in …` |
| `@AikidoSec ignore:`   | Finding does not apply                                                        | `@AikidoSec ignore: <specific reason>` then optional human rationale          |

Rules:

- Non-Aikido: exactly one taxonomy emoji, then one space, then the rest of the body. Do not stack extra decorative emoji after the prefix.
- **Aikido: first characters of the body are `@AikidoSec`.** Never prefix with emoji, markdown, or whitespace-only lines before the directive.
- Aikido feedback/ignore + Fixed in: directive first, blank line, then `Fixed in …` in the **same** comment (prefer one comment unless the user asks otherwise).
- Non-Aikido fix only: use **👍🏽**.
- Chat completion summaries may mirror taxonomy emojis for non-Aikido threads; for Aikido, say `feedback` / `ignore` without inventing a prefix emoji.

Preferred openers:

| Situation                        | Example                                                                                   |
| -------------------------------- | ----------------------------------------------------------------------------------------- |
| Fix pushed                       | `👍🏽 Fixed in [shortsha](https://github.com/<org>/<repo>/commit/FULL_SHA): <what changed>` |
| No change                        | `😇 Leaving this as-is because <reason>.`                                                 |
| Tip already has the fix          | `🆗 Already handled on the current branch. <evidence>. Leaving this thread as-is.`        |
| Valid polish, out of scope       | `📌 Accepted for this slice. <why not now>; further X can be a follow-up.`                |
| Stack/OpenSpec owns it later     | `🔜 … for this PR only. Later … in [#N](…).`                                              |
| Aikido ignore                    | `@AikidoSec ignore: <reason>`                                                             |
| Aikido feedback (+ optional fix) | `@AikidoSec feedback: <rule>` then optional blank line + `Fixed in …`                     |
| Need input                       | `❓ <question>`                                                                           |

Commit link formatting:

- Always lowercase org: `https://github.com/<org>/<repo>/commit/...`
- `Fixed in` label uses a **plain** short SHA: `[abc1234](url)` — not backtick-wrapped
- When the fix landed on another stack PR: `Fixed in [sha](…) (landed on the composition PR…): …`

### Link code symbols in replies

When a GitHub reply mentions a function, type, hook, constant, file, or other code symbol, wrap it in a markdown link to the remote blob at a known commit SHA with a line (or line range). Reviewers should be able to click straight to the definition or the line under discussion.

- Format: ``[`symbol`](https://github.com/OWNER/REPO/blob/<SHA>/<path>#L<n>)`` or `#Lstart-Lend` for ranges.
- Derive `<SHA>` mechanically from the PR branch tip (or the verified fix commit for post-fix links). Never invent or hand-type a SHA.
- Resolve line numbers from the file at that SHA before posting. After a fix commit, re-check lines that may have shifted.
- Prefer linking the symbol label itself (for example [`useEditorActiveSlide`](...#L16)), not a bare URL after the name.
- Link each distinct symbol the first time it appears in that reply. Do not leave bare backticks for call sites, types, or helpers you are arguing about.
- For removed code, link the pre-fix tip SHA (or drop that link and only link surviving call sites on the new SHA).
- Do **not** put code identifiers inside `@AikidoSec feedback:` / `ignore:` directive payloads; those stay machine-readable and PR-agnostic. Put blob links in the separate human rationale or `Fixed in` reply.

Example:

```markdown
😇 Leaving this as-is because [`useEditorActiveSlide`](https://github.com/<org>/<repo>/blob/abc1234…/packages/…/use-editor-active-slide.ts#L16) still returns the hybrid via [`getSlideProxy`](https://github.com/<org>/<repo>/blob/abc1234…/packages/…/use-editor-active-slide.ts#L23).
```

## Success Criteria

- Every relevant review comment (formal thread **or** human conversation comment) has a decision: act, dismiss, or ask.
- Every code change maps directly to a review comment.
- Edited code has scoped validation or an explicit validation caveat.
- Every accepted code change is committed and pushed to the PR branch before the related reply is posted.
- Every posted reply is concise, matches the decision, and uses the correct reply shape (taxonomy emoji prefix for non-Aikido; `@AikidoSec …` with **no** emoji for Aikido).
- Replies that name code symbols include GitHub blob+line links for those symbols (see **Link code symbols in replies**).
- Dismissals that defer work to later stack PRs name that handoff explicitly and link the follow-up PR(s) when known.
- Replies for implemented fixes include a verified GitHub commit link on the PR branch. Never post on GitHub about local, uncommitted, or unpushed work.
- Every completed formal review thread has one best-effort resolve attempt unless the user explicitly opted out.

## Workflow

1. Collect context:
   - Parse the PR owner, repo, and number from the URL.
   - Run `gh pr view <PR_URL> --json number,title,url,headRefName,baseRefName,author,reviewDecision`.
   - Fetch formal inline review threads, prioritizing unresolved threads unless the user asked for all comments.
   - Fetch PR conversation comments and formal review bodies (see below). Keep human review-like conversation comments in the triage set.
   - Read the changed files and local project instructions before editing.
   - On a high-reasoning host, prefer delegating this fetch/resolve work to a Grok subagent (see **Execution routing**).

2. Triage comments:
   - Act on comments that catch correctness bugs, regressions, maintainability issues, meaningful readability problems, missing tests, or clear repo convention violations.
   - Dismiss comments that are stylistic preferences already covered by repo conventions, would add unnecessary abstraction, conflict with product intent, or increase risk without meaningful benefit.
   - Ask the user before acting when the feedback changes product behavior, expands scope, or has more than one reasonable interpretation.
   - **Stale tip:** before implementing a "fix this" comment, check whether the PR tip already contains the behavior/test. If yes: do not re-fix; reply `🆗 Already handled/covered on the current branch. <evidence>. Leaving this thread as-is.` then resolve.
   - **Accept-without-fix (slice polish):** when the suggestion is reasonable but not a merge blocker for this PR's approved scope (nesting extract, rename, etc.), reply `📌 Accepted for this slice. …` rather than forcing a drive-by refactor. Do not "improve" adjacent code while addressing another comment (Karpathy + deslop).
   - **Deferred / stack / OpenSpec:** if the right answer is "not in this PR," say that explicitly (`🔜`). Prefer "for this PR only" and "not the final shape." Include the stack step or OpenSpec task id when known (`D5`, `P6`, `OpenSpec 4.6`, `Task 5.4`), the concrete follow-up PR link, and why moving it earlier would break the contract.
   - **Re-runs:** on a fresh `/pr-review-comments` (or equivalent) for the same PR, re-fetch threads. Only triage unresolved or new feedback. Do not re-reply to already-resolved threads unless the user asks to revise a specific reply.

3. Make changes:
   - Keep edits small and directly tied to the review comments (surgical: touch only what the comment requires).
   - Do not bundle unrelated cleanup. No new abstractions for one-off polish (for example Aikido nesting nits) unless the user asks to act.
   - No extra comments, speculative error handling, or `any` casts in the fix (deslop).
   - When the user asked to address or handle comments and a comment merits action, implement and validate its focused fix before posting a reply or resolving the thread.
   - Respect repository git rules. When a comment warrants a code change and the user asked to address or handle review feedback, commit the focused fix and push it to the PR branch; this is authorized by the skill.
   - **Never post a GitHub reply about uncommitted or unpushed work.** If a fix is not yet on the remote PR branch, keep that status in the chat completion summary only.
   - A reply for an implemented fix requires a verified GitHub commit link on the PR branch. Commit and push first, then reply.
   - Never type or reconstruct a full commit SHA manually. Derive it mechanically from Git/GitHub after the commit exists:
     `FULL_SHA=$(git rev-parse HEAD)` and `SHORT_SHA=$(git rev-parse --short=7 HEAD)`.
   - Before posting any reply that links to a commit, verify the linked commit resolves on GitHub:
     `gh api repos/OWNER/REPO/commits/$FULL_SHA --jq .sha`.
     If verification fails, do not post the fix reply on GitHub. Report the blocker in chat.

4. Validate:
   - Run IDE diagnostics on edited files when available.
   - Run the repo's scoped lint, typecheck, and tests for touched packages when practical.
   - If validation cannot be run, say so in the final summary and do not imply the code is verified.

5. Reply:
   - Reply to every in-scope comment after the decision is made. Posting replies is the default behavior for this skill; skip posting only when the user explicitly says not to post, not to comment, not to reply, or to keep everything local/in chat.
   - Prefix **non-Aikido** replies with the correct taxonomy emoji and one space (see **Reply taxonomy**).
   - **Link code symbols** (functions, types, hooks, constants, files) to remote blob+line URLs per **Link code symbols in replies**. Resolve SHA and line numbers before posting.
   - **Dismissals and no-change decisions:** reply on GitHub immediately.
   - Only when the original comment is authored by the Aikido bot (currently `aikido-pr-checks`, as in the Aikido link), use its learning directives when meaningful. Treat these directives as machine-readable training payloads, not resolution notes:
     - **The reply body must start with `@AikidoSec`.** Do not put any emoji (including 📡 / 🛡️), markdown, or other text before the directive — Aikido's parser will not fire.
     - Use `@AikidoSec feedback: <general rule>` only when the finding identifies a real issue but its diagnosis, severity, or suggested remedy should be improved in future reviews. The payload must be a standalone, reusable rule for similar code; do not include PR-specific facts, code identifiers, the implementation, validation, or a commit link.
     - Use `@AikidoSec ignore: <specific reason>` when the finding does not apply. State the concrete fact that invalidates the finding.
     - If a real fix was made, put `Fixed in [abc1234](...)` in the **same** comment after a blank line (do not mix it into the directive line). Prefer one comment unless the user asks otherwise.
     - Do not use either directive for other reviewers.
   - **Implemented fixes:** reply on GitHub only after the fix is committed, pushed, and the commit link is verified on GitHub. Until then, leave the item open and report status in chat.
   - If a change was made and a verified commit link is available on the PR branch, keep the reply concise and include a markdown link whose label is the short commit hash, followed by a short description of the fix. When the description names symbols, link those symbols to blob+line URLs:
     `👍🏽 Fixed in [abc1234](https://github.com/<org>/<repo>/commit/FULL_SHA): removed the extra [\`createEditorSlideCompatibilityLayer\`](https://github.com/<org>/<repo>/blob/PREV_SHA/path/File.tsx#L106) wrap — [\`useEditorActiveSlide\`](https://github.com/<org>/<repo>/blob/FULL_SHA/path/hook.ts#L16) already goes through [\`getSlideProxy\`](https://github.com/<org>/<repo>/blob/FULL_SHA/path/slides.ts#L55).`
   - If a change was made but there is no verified remote commit link yet, **do not post a reply on GitHub.** Leave the item open and report the blocker in chat.
   - The short description should be specific to the feedback, not a generic "addressed feedback". Prefer blob+line links over bare backticks when naming code. If one commit fixes several duplicate items, reuse the same verified commit link but tailor the description where useful.
   - If no change was made, keep the reply concise and explain why it is safe to dismiss, with linked symbols where you name them:
     `😇 Leaving this as-is because [\`getSlideById\`](https://github.com/<org>/<repo>/blob/SHA/path/slides.ts#L12) still keys off legacy \`id\`.`
   - When dismissing because later stack work owns the change, make the handoff obvious in the same reply, for example:
     `🔜 Keeping [\`Question[]\`](…#L26) here for this PR only. Later editor-lane PRs cut this over to canonical \`Slide\` (notably [#38399](https://github.com/<org>/<repo>/pull/38399) and follow-ups).`
   - Do not include long implementation summaries, validation logs, or unrelated details in replies.
   - **Plan-first:** if the user asks to plan, draft replies, or show what you will post before acting, draft the full triage and exact reply text in chat and wait for approval before posting, editing code, or resolving threads.
   - **Revise own replies:** if the user asks to update, clarify, or rewrite an already-posted reply you authored, edit that comment in place with `PATCH /repos/OWNER/REPO/pulls/comments/COMMENT_ID` instead of posting a duplicate thread reply. Keep blob+line links accurate (refresh SHA/lines if the tip moved).
   - Match reply channel to comment type:
     - Formal inline threads → thread reply (GraphQL below), then best-effort resolve.
     - Conversation comments → new PR conversation comment that `@`s the author and answers their points. Conversation comments cannot be "resolved"; the reply is the completion signal.
     - Formal review summary bodies with no inline thread → PR conversation comment that `@`s the reviewer.
   - After posting a reply for a completed formal thread decision, make one best-effort attempt to mark that review thread resolved by default. Skip resolving only if the user explicitly asks not to resolve threads. Do not resolve threads that still need user clarification, reviewer input, or follow-up work.
   - If resolving a thread fails, fail fast for that thread: do not retry in a loop or start unrelated troubleshooting. Report the unresolved thread and error in the completion summary.
   - Re-fetch review threads and conversation replies before finishing and confirm which formal threads resolved successfully.

## Fetching Formal Inline Threads

Use `gh api graphql` for thread state and comment URLs:

```bash
gh api graphql \
  -f owner=OWNER \
  -f repo=REPO \
  -F number=PR_NUMBER \
  -f query='
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          path
          line
          comments(first: 20) {
            nodes {
              id
              databaseId
              author { login }
              body
              url
              createdAt
            }
          }
        }
      }
    }
  }
}'
```

If there are more than 100 threads or 20 comments in a thread, paginate before deciding the work is complete.

## Fetching Conversation Comments And Review Bodies

Also fetch top-level PR conversation comments and submitted review bodies. Do this on every triage run, not only when formal threads are empty.

```bash
gh pr view PR_NUMBER --repo OWNER/REPO --json comments,reviews \
  --jq '{
    comments: [.comments[] | {author: .author.login, createdAt, url: .url, body}],
    reviews: [.reviews[] | {author: .author.login, state, submittedAt, body}]
  }'
```

Or via REST/GraphQL if you need pagination:

```bash
gh api repos/OWNER/REPO/issues/PR_NUMBER/comments --paginate
gh api repos/OWNER/REPO/pulls/PR_NUMBER/reviews --paginate
```

Filter to human, review-like items using **What Counts As Review Feedback**. Keep multi-point conversation reviews intact: triage each requested change, but one reply may cover several bullets when they share one decision or one commit.

## Replying To Formal Inline Threads

Prefer replying to the review thread with GraphQL:

```bash
gh api graphql \
  -f threadId=THREAD_ID \
  -f body='👍🏽 Fixed in [abc1234](https://github.com/<org>/<repo>/commit/FULL_SHA): removed the extra [`helper`](https://github.com/<org>/<repo>/blob/PREV_SHA/path/File.tsx#L106) wrap — [`useHook`](https://github.com/<org>/<repo>/blob/FULL_SHA/path/hook.ts#L16) already applies it.' \
  -f query='
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: $threadId,
    body: $body
  }) {
    comment { url }
  }
}'
```

If GraphQL is unavailable, reply to the specific review comment using REST:

```bash
gh api \
  -X POST \
  repos/OWNER/REPO/pulls/PR_NUMBER/comments/COMMENT_DATABASE_ID/replies \
  -f body='😇 Leaving this as-is because [`symbol`](https://github.com/<org>/<repo>/blob/SHA/path/file.ts#L12) still keys off legacy `id`.'
```

## Replying To Conversation Comments

Post a PR conversation comment that mentions the author:

```bash
gh api \
  -X POST \
  repos/OWNER/REPO/issues/PR_NUMBER/comments \
  -f body="$(cat <<'EOF'
@AUTHOR 👍🏽 Fixed in [abc1234](https://github.com/<org>/<repo>/commit/FULL_SHA): <short description>.

EOF
)"
```

For dismissals:

```bash
gh api \
  -X POST \
  repos/OWNER/REPO/issues/PR_NUMBER/comments \
  -f body="$(cat <<'EOF'
@AUTHOR 😇 Leaving this as-is because <brief reason>.

EOF
)"
```

If the conversation comment lists several findings, structure the reply with short bullets that map 1:1 to those findings (fixed / leaving as-is / asking).

## Editing An Existing Reply

When the user wants a posted reply changed (clearer deferred handoff, better links, tone, etc.) and you authored that comment:

```bash
gh api \
  -X PATCH \
  repos/OWNER/REPO/pulls/comments/COMMENT_DATABASE_ID \
  -f body='😇 Updated reply text with [`symbol`](https://github.com/<org>/<repo>/blob/SHA/path/file.ts#L12) links.'
```

Prefer edit-in-place over a second reply on the same thread unless the user wants an additional follow-up or the decision itself changed (for example dismiss → fix).

## Resolving Formal Threads

After replying to a formal thread whose decision is complete, make one best-effort attempt to resolve it with GraphQL:

```bash
gh api graphql \
  -f threadId=THREAD_ID \
  -f query='
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread { id isResolved }
  }
}'
```

Re-fetch the review threads afterward and verify which replied-to threads have `isResolved: true`. If a resolve attempt failed, do not keep retrying unless the user explicitly asks; include the failure in the completion summary.

Conversation comments have no resolve API. Do not pretend they were resolved; report that you replied instead.

## Completion Summary

End with a concise summary:

- Which comments were changed.
- Which comments were dismissed and why.
- Which replies were posted (formal threads and conversation comments; only after verified remote commits for fixes). Prefer mirroring taxonomy emojis in the list.
- Which formal review threads were resolved, which remain open intentionally (including items waiting on commit/push), and which failed best-effort resolution.
- Which conversation-comment reviews were answered.
- Which validation ran and whether it passed.
- Note missing companion skills or skipped Grok routing only when relevant.
