# Agent Skills

Reusable agent skills.

## Install

```bash
npx skills add rebelliard/agents
```

Install a single skill:

```bash
npx skills add https://github.com/rebelliard/agents --skill adversarial-review
npx skills add https://github.com/rebelliard/agents --skill frame-analysis-gif
npx skills add https://github.com/rebelliard/agents --skill frame-analysis-video
npx skills add https://github.com/rebelliard/agents --skill orchestrate
npx skills add https://github.com/rebelliard/agents --skill pr-stack-planner
npx skills add https://github.com/rebelliard/agents --skill pr-review-comments
```

## Included skills

- `adversarial-review`: runs cold-context adversarial review for
  agent-written or high-risk code changes.
- `frame-analysis-gif`: analyzes animated GIF, WebP, and APNG files as
  ordered frame sequences.
- `frame-analysis-video`: analyzes video files and screen recordings as
  ordered frame sequences.
- `orchestrate`: coordinates ambitious, multi-workstream goals through adaptive
  delegation, central verification, and final synthesis.
- `pr-stack-planner`: analyzes large changes and drafts self-contained,
  dependency-aware PR stack strategies for GitHub comments or Markdown
  handoffs.
- `pr-review-comments`: triages and addresses GitHub PR review feedback with
  focused fixes, verified commit replies, and taxonomy emoji prefixes.
