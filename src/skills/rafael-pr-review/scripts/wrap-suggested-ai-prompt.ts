import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Max visible width for Suggested AI prompt bodies inside GitHub ```text fences. */
export const SUGGESTED_AI_PROMPT_WIDTH = 80;

const LIST_MARKER_PATTERN = /^(\d+\.\s+|[-*•]\s+)/;
const PR_BRANCH_OPENER_PATTERN =
  /^On PR (\S+) \(branch ([^)\n]+)\),\s*([^\n]+)(\n[\s\S]*)?$/;

export type BuildSuggestedAiPromptInput = {
  postPath: string;
  postLine: number;
  suggestedChange: string;
  evidence: string;
  /** Optional PR URL for the preferred opener shape. */
  prUrl?: string;
  /** Optional head branch; rendered as `- Branch: ` + formatInlineCode(name). */
  headRef?: string;
};

/**
 * Wrap a code expression for Markdown inline code without breaking when the
 * value already contains backticks.
 *
 * Examples:
 * - `EditorSlideHost` → `EditorSlideHost`
 * - `foo`bar` → `` foo`bar ``
 * - `` `already` `` → `` `already` `` (padded; delimiter one longer than inner)
 */
export function formatInlineCode(value: string): string {
  const longest = longestBacktickRun(value);
  const fence = "`".repeat(longest + 1);
  const needsPad =
    value.startsWith("`") ||
    value.endsWith("`") ||
    value.startsWith(" ") ||
    value.endsWith(" ");
  const inner = needsPad ? ` ${value} ` : value;
  return `${fence}${inner}${fence}`;
}

/** Longest consecutive backtick run in `value` (0 when none). */
export function longestBacktickRun(value: string): number {
  let longest = 0;
  let run = 0;
  for (const char of value) {
    if (char === "`") {
      run += 1;
      longest = Math.max(longest, run);
      continue;
    }
    run = 0;
  }
  return longest;
}

/**
 * Choose an opening/closing fence for the Suggested AI prompt body so embedded
 * ``` sequences cannot terminate the fence early.
 */
export function choosePromptBodyFence(body: string): {
  open: string;
  close: string;
} {
  const fence = "`".repeat(Math.max(3, longestBacktickRun(body) + 1));
  return { open: `${fence}text`, close: fence };
}

/**
 * Normalize Suggested AI prompt body authoring before wrap:
 * - Rewrite `On PR <url> (branch <name>), <goal>` into a clean opener plus
 *   `- Branch: <inline-code>` bullet (skips when a branch bullet already exists).
 */
export function normalizeSuggestedAiPromptText(text: string): string {
  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const match = normalized.match(PR_BRANCH_OPENER_PATTERN);
  if (match === null) {
    return normalized;
  }

  const url = match[1] ?? "";
  const branch = (match[2] ?? "").trim();
  const goal = (match[3] ?? "").trim();
  const remainder = match[4] ?? "";
  const branchBullet = `- Branch: ${formatInlineCode(branch)}`;

  if (
    remainder.includes(branchBullet) ||
    new RegExp(
      `^-\\s*[Bb]ranch:\\s*${escapeRegExp(formatInlineCode(branch))}`,
      "m",
    ).test(remainder) ||
    new RegExp(`^-\\s*[Bb]ranch:\\s*\`${escapeRegExp(branch)}\``, "m").test(
      remainder,
    )
  ) {
    return `On PR ${url}, ${goal}${remainder}`;
  }

  return `On PR ${url}, ${goal}\n${branchBullet}${remainder}`;
}

/**
 * Prepare prompt body for posting: normalize opener/branch shape, then wrap.
 */
export function prepareSuggestedAiPromptText(
  text: string,
  width = SUGGESTED_AI_PROMPT_WIDTH,
): string {
  return wrapSuggestedAiPromptText(normalizeSuggestedAiPromptText(text), width);
}

/**
 * Word-wrap prompt body text to `width` columns.
 *
 * - Preserves blank lines and existing leading indentation.
 * - Numbered / bullet list items use a hanging indent equal to the marker width
 *   so continuations stay aligned under the item text.
 * - Inline code spans stay atomic (including multi-backtick CommonMark fences;
 *   not split across lines mid-span).
 * - Tokens longer than the remaining width (URLs, long paths, long code spans)
 *   stay unbroken on their own line rather than being mid-token split.
 */
export function wrapSuggestedAiPromptText(
  text: string,
  width = SUGGESTED_AI_PROMPT_WIDTH,
): string {
  if (width < 1) {
    throw new Error(
      `wrapSuggestedAiPromptText: width must be >= 1, got ${width}`,
    );
  }

  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const lines = normalized.split("\n");
  const wrapped: string[] = [];

  for (const line of lines) {
    wrapped.push(...wrapLine(line, width));
  }

  return wrapped.join("\n");
}

/**
 * Assemble the standard Suggested AI prompt details block with an 80-col wrapped
 * body. Prefer this over hand-rolling the fence so wrap is never skipped.
 * The body fence length grows when the body contains backtick runs so ``` inside
 * the prompt cannot close the fence early.
 */
export function buildSuggestedAiPromptBlock(
  input: BuildSuggestedAiPromptInput,
  width = SUGGESTED_AI_PROMPT_WIDTH,
): string {
  const pathCode = formatInlineCode(input.postPath);
  const opening =
    input.prUrl === undefined
      ? `Address this review finding in ${pathCode} at line ${input.postLine}.`
      : `On PR ${input.prUrl}, address the finding in ${pathCode} at line ${input.postLine}.`;

  const parts = [opening];
  if (input.headRef !== undefined && input.headRef.trim().length > 0) {
    parts.push(`- Branch: ${formatInlineCode(input.headRef.trim())}`);
  }
  parts.push(
    "",
    input.suggestedChange.trim(),
    "",
    `Evidence: ${input.evidence.trim()}`,
    "",
    "Keep the change focused, add or update a regression test when appropriate, and run the relevant validation.",
  );

  const body = prepareSuggestedAiPromptText(parts.join("\n"), width);
  const fence = choosePromptBodyFence(body);

  return [
    "<details>",
    "<summary>✨ Suggested AI prompt</summary>",
    "",
    fence.open,
    body,
    fence.close,
    "",
    "</details>",
    "",
  ].join("\n");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split on whitespace while keeping inline code spans intact, including
 * CommonMark multi-backtick fences such as `` foo`bar ``.
 */
export function tokenizePromptContent(content: string): string[] {
  const tokens: string[] = [];
  let index = 0;

  while (index < content.length) {
    const char = content[index];
    if (char === undefined) {
      break;
    }

    if (/\s/.test(char)) {
      index += 1;
      continue;
    }

    if (char === "`") {
      let openLen = 0;
      while (content[index + openLen] === "`") {
        openLen += 1;
      }

      let search = index + openLen;
      let closed = false;
      while (search < content.length) {
        if (content[search] !== "`") {
          search += 1;
          continue;
        }

        let closeLen = 0;
        while (content[search + closeLen] === "`") {
          closeLen += 1;
        }

        if (closeLen === openLen) {
          tokens.push(content.slice(index, search + closeLen));
          index = search + closeLen;
          closed = true;
          break;
        }

        search += closeLen;
      }

      if (closed) {
        continue;
      }

      // Unclosed fence on this line — keep an adjacent info-string (e.g. ```ts)
      // in the same token so wrap does not insert a space (``` ts).
      let end = index + openLen;
      while (end < content.length) {
        const next = content[end];
        if (next === undefined || /\s/.test(next)) {
          break;
        }
        end += 1;
      }
      tokens.push(content.slice(index, end));
      index = end;
      continue;
    }

    let end = index + 1;
    while (end < content.length) {
      const next = content[end];
      if (next === undefined || /\s/.test(next) || next === "`") {
        break;
      }
      end += 1;
    }
    tokens.push(content.slice(index, end));
    index = end;
  }

  return tokens;
}

function wrapLine(line: string, width: number): string[] {
  if (line.length === 0) {
    return [""];
  }

  const indentMatch = line.match(/^[ \t]*/);
  const indent = indentMatch?.[0] ?? "";
  const withoutIndent = line.slice(indent.length);

  if (withoutIndent.length === 0) {
    return [indent];
  }

  const markerMatch = withoutIndent.match(LIST_MARKER_PATTERN);
  const marker = markerMatch?.[1] ?? "";
  const content = withoutIndent.slice(marker.length);
  const firstPrefix = `${indent}${marker}`;
  const continuationPrefix = `${indent}${" ".repeat(marker.length)}`;

  const tokens = tokenizePromptContent(content);

  if (tokens.length === 0) {
    return [firstPrefix.trimEnd()];
  }

  const output: string[] = [];
  let prefix = firstPrefix;
  let current = "";
  let lastToken = "";

  for (const token of tokens) {
    const glue = shouldGlueToPrevious(lastToken, token);

    if (current.length === 0) {
      const firstAttempt = `${prefix}${token}`;
      if (firstAttempt.length <= width || prefix.length === 0) {
        current = firstAttempt;
        lastToken = token;
        continue;
      }

      // Prefix leaves no room for this token — emit the marker line alone, then
      // place the long token on a hanging-indent line (may exceed width).
      if (prefix.trim().length > 0) {
        output.push(prefix.trimEnd());
      }
      prefix = continuationPrefix;
      current = `${prefix}${token}`;
      lastToken = token;
      continue;
    }

    const candidate = glue ? `${current}${token}` : `${current} ${token}`;
    if (candidate.length <= width) {
      current = candidate;
      lastToken = token;
      continue;
    }

    output.push(current);
    prefix = continuationPrefix;
    current = `${prefix}${token}`;
    lastToken = token;
  }

  if (current.length > 0) {
    output.push(current);
  }

  return output;
}

/** Avoid `code` , / `code` ) artifacts when punctuation is its own token. */
function shouldGlueToPrevious(previous: string, next: string): boolean {
  if (previous.length === 0) {
    return false;
  }
  if (/^[.,:;!?)]+$/.test(next)) {
    return true;
  }
  if (/^[({[]+$/.test(previous)) {
    return true;
  }
  // Keep `all-`undefined`` / `no/`path`` style prefixes attached to code spans.
  if (/[-/]$/.test(previous) && next.startsWith("`")) {
    return true;
  }
  return false;
}

async function readStdin(): Promise<string> {
  return await new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk: string) => {
      data += chunk;
    });
    process.stdin.on("end", () => {
      resolve(data);
    });
    process.stdin.on("error", reject);
  });
}

async function runCli(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] === "--build") {
    const inputPath = args[1];
    const rawInput =
      inputPath === undefined
        ? await readStdin()
        : readFileSync(inputPath, "utf8");
    const parsed = JSON.parse(rawInput) as BuildSuggestedAiPromptInput;
    process.stdout.write(buildSuggestedAiPromptBlock(parsed));
    return;
  }

  const inputPath = args[0];
  const rawInput =
    inputPath === undefined
      ? await readStdin()
      : readFileSync(inputPath, "utf8");
  // Preserve a trailing newline when the input had one, matching typical
  // filter-script behavior for prompt bodies.
  const hadTrailingNewline = rawInput.endsWith("\n");
  const wrapped = prepareSuggestedAiPromptText(rawInput.replace(/\n$/, ""));
  process.stdout.write(hadTrailingNewline ? `${wrapped}\n` : wrapped);
}

function isCliEntryPoint(): boolean {
  const entryPoint = process.argv[1];
  if (entryPoint === undefined) {
    return false;
  }

  return fileURLToPath(import.meta.url) === path.resolve(entryPoint);
}

if (isCliEntryPoint()) {
  void runCli();
}
