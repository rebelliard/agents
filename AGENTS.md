# Coding Instructions

This repository contains reusable agent tooling. It currently focuses on agent skills, with room for
other agentic work over time.

## Package Manager

Use `pnpm` for all commands.

## Project Shape

- Source folders live under `src/`.
- Each skill should have its own folder, named with lowercase kebab-case.
- Each skill folder should include a `SKILL.md` entrypoint with `name` and `description` YAML frontmatter.
- Install local skills by symlinking skills from `src/skills/` into `.agents/skills`.
- Keep repo tests outside published skill folders. Put skill tests under `tests/skills/`, not under
  `src/skills/<skill-name>/`, so installed or packaged skills do not include test files.

## Validation Strategy

Run focused validation on what you changed.

### Formatting

- Rewrite TypeScript, JavaScript, JSON, and other non-Markdown files with
  `pnpm exec biome check --write <file-or-path>`.
- Verify with `pnpm exec biome ci <file-or-path>` before finishing.
- Python uses standard-library formatting conventions in this repo for now. Validate Python changes
  with `python3 -B -m unittest discover -s tests` or `pnpm test`; pre-commit only compiles staged
  Python files.
- Markdown and MDX use Prettier with `.git-hooks/prettierrc.markdown.json` only. Do not add a
  repo-wide `.prettierrc`.
- For agent-authored Markdown (`*.md`, `*.mdx`), wrap prose at roughly 80 columns. This includes
  skill docs, automation docs, prompt docs, and YAML frontmatter descriptions. Do not reflow
  tables, code blocks, URLs, or generated inventory when wrapping would hurt readability.
- Lefthook pre-commit runs Biome and Prettier on staged files when installed. Cursor and Claude
  editor hooks use the same Markdown config.

### Before Completing A Task

Run these when they apply to your change:

```bash
pnpm format:check
pnpm tc
pnpm test
```

`pnpm check` runs format check, typecheck, and tests together.
