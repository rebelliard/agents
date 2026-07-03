# Markdown Formatting

Biome is the repo-wide formatter for TypeScript, JavaScript, JSON, and other non-Markdown files.
`biome.json` excludes `**/*.md`, so do not add a root `.prettierrc`.

Markdown and MDX use Prettier 3 with `.git-hooks/prettierrc.markdown.json`.

## When It Runs

- Pre-commit: `format-markdown` runs `.git-hooks/format-staged-markdown.sh`.
- Editor hooks: `.claude/hooks/markdown-format.sh` and `.cursor/hooks.json` use the same config path.

## Manual Commands

For touched Markdown only:

```bash
pnpm exec prettier --config .git-hooks/prettierrc.markdown.json --write path/to/file.md
```

Run Biome on code paths and Prettier with this config on Markdown paths.
