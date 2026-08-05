import { describe, expect, it } from "vitest";
import {
  buildSuggestedAiPromptBlock,
  choosePromptBodyFence,
  formatInlineCode,
  normalizeSuggestedAiPromptText,
  prepareSuggestedAiPromptText,
  SUGGESTED_AI_PROMPT_WIDTH,
  tokenizePromptContent,
  wrapSuggestedAiPromptText,
} from "../../../src/skills/rafael-pr-review/scripts/wrap-suggested-ai-prompt";

describe("normalizeSuggestedAiPromptText", () => {
  it("splits parenthetical branch into a branch bullet", () => {
    const input =
      "On PR https://github.com/mentimeter/mm-js/pull/38773 (branch lit/lit-758-prop-driven-presentations), restore or explicitly accept the mobile quiz-open no-results correct-answer line.\n\nProblem:\n- something";

    expect(normalizeSuggestedAiPromptText(input)).toBe(
      [
        "On PR https://github.com/mentimeter/mm-js/pull/38773, restore or explicitly accept the mobile quiz-open no-results correct-answer line.",
        "- Branch: `lit/lit-758-prop-driven-presentations`",
        "",
        "Problem:",
        "- something",
      ].join("\n"),
    );
  });

  it("does not duplicate an existing branch bullet", () => {
    const input = [
      "On PR https://example.com/pr/1 (branch feature/x), do the thing.",
      "- Branch: `feature/x`",
      "",
      "Do:",
      "1. step",
    ].join("\n");

    expect(normalizeSuggestedAiPromptText(input)).toBe(
      [
        "On PR https://example.com/pr/1, do the thing.",
        "- Branch: `feature/x`",
        "",
        "Do:",
        "1. step",
      ].join("\n"),
    );
  });
});

describe("formatInlineCode", () => {
  it("wraps plain expressions in single backticks", () => {
    expect(formatInlineCode("EditorSlideHost")).toBe("`EditorSlideHost`");
  });

  it("uses a longer fence when the value already contains backticks", () => {
    expect(formatInlineCode("foo`bar")).toBe("``foo`bar``");
    expect(formatInlineCode("`already`")).toBe("`` `already` ``");
  });
});

describe("choosePromptBodyFence", () => {
  it("uses ``` by default", () => {
    expect(choosePromptBodyFence("no ticks here")).toEqual({
      open: "```text",
      close: "```",
    });
  });

  it("lengthens the fence when the body contains ```", () => {
    expect(choosePromptBodyFence("example:\n```ts\nconst x = 1;\n```")).toEqual(
      {
        open: "````text",
        close: "````",
      },
    );
  });
});

describe("tokenizePromptContent", () => {
  it("keeps inline code spans as atomic tokens", () => {
    expect(
      tokenizePromptContent(
        "uses `Boolean(CanvasVisualizationArea) && !hasResults` in path",
      ),
    ).toEqual([
      "uses",
      "`Boolean(CanvasVisualizationArea) && !hasResults`",
      "in",
      "path",
    ]);
  });

  it("keeps multi-backtick inline code spans atomic", () => {
    expect(tokenizePromptContent("see ``foo`bar`` please")).toEqual([
      "see",
      "``foo`bar``",
      "please",
    ]);
  });
});

describe("wrapSuggestedAiPromptText", () => {
  it("leaves short lines unchanged", () => {
    const input = "Keep the fix minimal.\n\nDo not expand scope.";
    expect(wrapSuggestedAiPromptText(input)).toBe(input);
  });

  it("wraps long prose at 80 columns on word boundaries", () => {
    const input =
      "Prefer threading an explicit boolean from the host that stays true on mobile and desktop editor surfaces so the no-results correct-answer line still renders.";

    const wrapped = wrapSuggestedAiPromptText(input);
    const lines = wrapped.split("\n");

    expect(lines.length).toBeGreaterThan(1);
    for (const line of lines) {
      expect(line.length).toBeLessThanOrEqual(SUGGESTED_AI_PROMPT_WIDTH);
    }
    expect(wrapped.replace(/\n/g, " ")).toBe(input);
  });

  it("hangs numbered-list continuations under the item text", () => {
    const input =
      "1. Prefer threading an explicit boolean from the host (e.g. isEditorSurface / showEditorNoResultsAnswer) that stays true on mobile+desktop editor, and gate isEditorWithoutResults on that";

    const wrapped = wrapSuggestedAiPromptText(input);
    const lines = wrapped.split("\n");

    expect(lines[0]?.startsWith("1. ")).toBe(true);
    expect(lines.length).toBeGreaterThan(1);
    for (const line of lines.slice(1)) {
      expect(line.startsWith("   ")).toBe(true);
      expect(line.startsWith("    ")).toBe(false);
    }
    for (const line of lines) {
      expect(line.length).toBeLessThanOrEqual(SUGGESTED_AI_PROMPT_WIDTH);
    }
  });

  it("hangs bullet continuations under the item text", () => {
    const input =
      "- `isEditorWithoutResults` now uses Boolean(CanvasVisualizationArea) && !hasResults in packages/slides-presentation/src/slide-types/quiz-open/ViewOnlyPresentationDataHandler.tsx on purpose";

    const wrapped = wrapSuggestedAiPromptText(input);
    const lines = wrapped.split("\n");

    expect(lines[0]?.startsWith("- ")).toBe(true);
    expect(lines.length).toBeGreaterThan(1);
    for (const line of lines.slice(1)) {
      expect(line.startsWith("  ")).toBe(true);
      expect(line.startsWith("   ")).toBe(false);
    }
  });

  it("does not split inside an inline code span", () => {
    const code = "`Boolean(CanvasVisualizationArea) && !hasResults`";
    const input = `- uses ${code} today on purpose with extra prose after the span`;
    const wrapped = wrapSuggestedAiPromptText(input);

    expect(wrapped).toContain(code);
    expect(wrapped.includes("&&\n")).toBe(false);
  });

  it("keeps punctuation glued after inline code spans", () => {
    const wrapped = wrapSuggestedAiPromptText(
      "Mobile `EditorSlideHost` forwards `moduleProps = {}`, so `CanvasVisualizationArea` is always `undefined`.",
    );

    expect(wrapped).toContain("`moduleProps = {}`,");
    expect(wrapped.includes("` ,")).toBe(false);
    expect(wrapped).toContain("`undefined`.");
  });

  it("keeps hyphen prefixes glued to following code spans", () => {
    const wrapped = wrapSuggestedAiPromptText(
      "the ICE bag was a truthy object of all-`undefined` fields",
    );

    expect(wrapped).toContain("all-`undefined`");
    expect(wrapped.includes("all- `undefined`")).toBe(false);
  });

  it("preserves blank lines and existing indentation", () => {
    const input = [
      "Problem:",
      "- short item",
      "",
      "Do:",
      "1. first step that is long enough to wrap across multiple columns because the sentence keeps going past eighty characters easily",
      "2. ertc",
    ].join("\n");

    const wrapped = wrapSuggestedAiPromptText(input);
    expect(wrapped.split("\n")).toContain("");
    expect(wrapped).toContain("Problem:");
    expect(wrapped).toContain("2. ertc");
    expect(wrapped.split("\n").some((line) => line.startsWith("   "))).toBe(
      true,
    );
  });

  it("does not mid-split unsplittable tokens longer than the width", () => {
    const url =
      "https://github.com/mentimeter/mm-js/blob/3c12f9047c50941dd1877247bdab80630bf96dfc/packages/slides-presentation/src/slide-types/quiz-open/ViewOnlyPresentationDataHandler.tsx";
    const wrapped = wrapSuggestedAiPromptText(`See ${url} for details.`);
    expect(wrapped).toContain(url);
    expect(wrapped.split(/\s+/)).toContain(url);
  });

  it("rejects non-positive widths", () => {
    expect(() => {
      wrapSuggestedAiPromptText("hello", 0);
    }).toThrow(/width must be >= 1/);
  });
});

describe("prepareSuggestedAiPromptText", () => {
  it("normalizes the PR opener then wraps", () => {
    const prepared = prepareSuggestedAiPromptText(
      "On PR https://github.com/mentimeter/mm-js/pull/38773 (branch lit/lit-758-prop-driven-presentations), restore or explicitly accept the mobile quiz-open no-results correct-answer line.",
    );

    expect(
      prepared.startsWith(
        "On PR https://github.com/mentimeter/mm-js/pull/38773,",
      ),
    ).toBe(true);
    expect(prepared).toContain(
      "- Branch: `lit/lit-758-prop-driven-presentations`",
    );
    expect(prepared.includes("(branch ")).toBe(false);
    for (const line of prepared.split("\n")) {
      expect(line.length).toBeLessThanOrEqual(SUGGESTED_AI_PROMPT_WIDTH);
    }
  });
});

describe("buildSuggestedAiPromptBlock", () => {
  it("returns a details fence with wrapped text body", () => {
    const block = buildSuggestedAiPromptBlock({
      postPath:
        "packages/slides-presentation/src/slide-types/quiz-open/ViewOnlyPresentationDataHandler.tsx",
      postLine: 45,
      suggestedChange:
        "1. Prefer threading an explicit boolean from the host that stays true on mobile and desktop editor surfaces and gate isEditorWithoutResults on that value instead of CanvasVisualizationArea presence",
      evidence:
        "Mobile EditorSlideHost forwards moduleProps = {}, so CanvasVisualizationArea is always undefined and the NoResultsCorrectAnswer line never shows on the default zero-response path",
    });

    expect(block).toContain("<summary>✨ Suggested AI prompt</summary>");
    expect(block).toContain("```text\n");
    expect(block.endsWith("</details>\n")).toBe(true);
    expect(block).toContain(
      "`packages/slides-presentation/src/slide-types/quiz-open/ViewOnlyPresentationDataHandler.tsx`",
    );

    const body = block.split("```text\n")[1]?.split("\n```")[0] ?? "";
    for (const line of body.split("\n")) {
      if (line.includes("http") || line.includes("/")) {
        // Long paths/URLs may exceed width when unsplittable.
        continue;
      }
      expect(line.length).toBeLessThanOrEqual(SUGGESTED_AI_PROMPT_WIDTH);
    }
    expect(body).toContain("1. Prefer");
    expect(body).toMatch(/\n {3}\S/);
  });

  it("uses On PR + branch bullet when prUrl/headRef are provided", () => {
    const block = buildSuggestedAiPromptBlock({
      postPath: "packages/user/src/rollout-routing.ts",
      postLine: 10,
      prUrl: "https://github.com/mentimeter/mm-js/pull/38773",
      headRef: "lit/lit-758-prop-driven-presentations",
      suggestedChange: "Fix the thing.",
      evidence: "See the test.",
    });

    const body = block.split("```text\n")[1]?.split("\n```")[0] ?? "";
    expect(body).toContain(
      "On PR https://github.com/mentimeter/mm-js/pull/38773, address the finding",
    );
    expect(body).toContain("- Branch: `lit/lit-758-prop-driven-presentations`");
  });

  it("lengthens the body fence when suggestedChange contains a ``` run", () => {
    const block = buildSuggestedAiPromptBlock({
      postPath: "src/example.ts",
      postLine: 1,
      suggestedChange: "Replace with:\n```ts\nconst ok = true;\n```",
      evidence: "Broken fence risk.",
    });

    expect(block).toMatch(/\n````text\n/);
    expect(block).toMatch(/\n````\n\n<\/details>/);
    expect(block).not.toMatch(/\n```text\n/);
    expect(block).toContain("```ts\n");
    expect(block.includes("``` ts")).toBe(false);
  });
});
