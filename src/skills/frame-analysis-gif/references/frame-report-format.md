# GIF Frame Report Format

Use this literal skeleton after extracting and reading the GIF contact
sheets. The report format is part of the skill's contract, not a style
suggestion.

## Internal vs user output

Tile numbers (`sampled[].tile`, sheet ranges like `"13-24"`) anchor the
agent's reasoning while reading contact sheets. They are **not** shown in
the user-facing report — users cannot see the sheets, and opaque tile IDs
add noise without verifiability. Timestamps in the timeline
(`sampled[].t`) are the user-verifiable anchor against the original GIF.

When the user asks for proof or evidence on follow-up, attach pertinent
frame PNGs from the retained `outDir` (see the skill's on-demand evidence
workflow).

## Template

The emoji heading prefixes are fixed: 🎬 summary, 🖼️ initial state, ▶️
timeline, ⚠️ analysis notes. Use them exactly so every report renders the
same sections the same way.

```markdown
### 🎬 Animation summary

<one sentence: what the GIF demonstrates overall; wrap total duration markers like `~26s` in backticks>

### 🖼️ Initial state

<bulleted list describing the first frame before anything moves>

- <app/site and screen shown, overall layout>
- <visible chrome: sidebars, panels, toolbars, modals>
- <active tab / selected item in any tab view, list, or navigation>
- <where user focus appears to be: focused input, visible text caret, cursor position>
- <starting values later steps depend on (form contents, counters, statuses)>

### ▶️ Timeline

1. **<2-5 word change label>** (`~t=<start>–<end>s`): <what changed>
2. **<2-5 word change label>** (`~t=<start>–<end>s`): <what changed>
   ...

### ⚠️ Analysis notes

- <coverage note from helper JSON: sampled coverage, dropped changes, or
  "All image changes were detected and included in the analysis.">
- <loop note when loopClosed is known: "Animation does not loop." or "The animation loops back to its first frame.">
- <anything relevant to interpreting the analysis; never mention sheet labeling or drawtext availability>

🔍 You can **ask for evidence** (e.g. "show evidence of steps 5 and 6").
```

## Writing Rules

- This template applies even when the user requests a specific output
  shape ("a numbered list", "describe what you see", "list the steps") —
  fulfill that request within the sections: the ▶️ Timeline is the
  numbered list; static context goes under 🖼️ Initial state.
- The timeline is a markdown numbered list (`1.`, `2.`, …) — never
  `Step N` prose. Each entry must use this exact compact grammar:
  ``<n>. **<2-5 word change label>** (`~t=<start>–<end>s`): <what changed>``.
- Use the same timestamp format everywhere in the report — timeline,
  summary, and analysis notes: approximate marker `~t=`, one decimal place
  when useful, an en dash between start and end, and the trailing `s`
  after the end time. Wrap every time reference in backticks, including
  total duration in the summary (`~26s`) and ranges cited in analysis
  notes (`~t=6–11s`).
  Good:
  ``3. **New slide picker** (`~t=13.2–14.3s`): The user opens the slide-type menu.``
  ``A `~26s` Chrome screen recording: …``
  ``…typing deltas between `~t=6–11s` and `~t=22–25s` may be missing.``
  Bad: `New slide picker (~t=13.2–14.3s): ...`, `A ~26s Chrome screen recording`, or
  `between ~t=6–11s` without backticks.
- Timeline range endpoints are evidence bounds, not exact event timings:
  the start is the last sampled time before or at the visible change, and
  the end is the first sampled time where the new state is visible. If the
  trigger is not directly visible, keep the bracketing range and say the
  change happens between those times.
- The bold label names the change, not the UI state. Keep it short and
  concrete: "Address bar typing", "Dashboard loads", "New slide picker",
  "Title edited".
- The Analysis notes section is a bulleted list.
- Do not append tile numbers or `— evidence: tiles …` suffixes to Initial
  state or timeline entries.
- Initial state is a bulleted list, not paragraphs.
- Initial state should estimate where the user's focus/input currently is
  when the sampled frames support it — a focused input, a visible text
  caret, or the cursor position — and name visible structure such as open
  sidebars/panels and which tab is active in a tab view.
- Every timeline step must describe something _changing_. If a line
  describes what is simply visible, it belongs in Initial state.
- Start the timeline at the first observed change; do not spend steps
  re-describing static context.
- Keep Initial state brief — only the context needed to understand the
  steps.
- Describe changes between sampled states, not every tile as a standalone
  screenshot.
- If `droppedChangeCount` is 0, every visual change was captured —
  describe the actions as observed, with no "inferred between samples"
  hedging. In Analysis notes, say "All image changes were detected and
  included in the analysis."
- If the transition cause is not visible between sampled frames, say
  between `` `~t=X–Ys` `` (plain "between", backticked range).
- If only the first frame or a rasterized preview is available, do not
  use this timeline template.
- Always include GIF loop status when `loopClosed` is known. If the GIF
  loops back to the start, do not treat wraparound as a new final state.
- Never include sheet-labeling or `drawtext` details in the user-facing
  report. Unlabeled contact sheets are an internal tooling detail, not
  useful analysis context.
- Append the evidence footnote verbatim after the Analysis notes bullets
  (blank line before it). It is not a fifth heading — do not wrap it in a
  section.
- Include the footnote when the full four-section report is used. Skip it
  for static images, rasterized previews, extraction errors, evidence-only
  follow-ups, or when the user already asked for evidence in the same
  turn.
- Omit or generalize secrets, tokens, private messages, and other PII when
  composing Initial state, Timeline, and captions — this mirrors the
  SKILL's redaction rules at the point of composition, not just at frame
  review time.

## Determinism checklist

Before sending, compare the draft against this checklist and fix every
mismatch:

- Exactly four section headings, in this order, using the literal emoji
  prefixes from the template.
- Timeline entries all match the compact grammar:
  ``<n>. **<label>** (`~t=<start>–<end>s`): <what changed>``.
- No prose-only timeline labels such as `<label> (~t=...):`; the label
  must be bold and the timestamp must be in backticks.
- Summary and analysis notes use the same backticked time format as the
  timeline — no bare `~t=…` or `~Ns` outside backticks.
- Analysis notes include relevant coverage and GIF loop status, but omit
  sheet-labeling and `drawtext` details.
- The evidence footnote appears exactly as shown in the template unless
  the skip rules above apply.
