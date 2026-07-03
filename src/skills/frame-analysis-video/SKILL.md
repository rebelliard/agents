---
name: frame-analysis-video
description: >-
  Analyze video files as ordered frame sequences. Use when a video file is
  attached, pasted, referenced, or discovered in the working set, or when
  the user asks what happens in a recording or screen recording and the
  available source is a video container. Common trigger extensions include
  .mp4, .mov, .webm, .mkv, .m4v, .mpeg, and .mpg.
---

# Video Frame Analysis

Use this skill when the user provides or references a video file and the
answer depends on motion, timing, UI state changes, or user actions across
the recording.

For the response skeleton, see
[frame-report-format.md](references/frame-report-format.md).

## Core Rule

Never describe a video from a single visible frame when the task depends on
time or motion. First prove that the original video bytes are available.

### Sensitive content

If frames show secrets, tokens, private messages, or other PII, omit or
generalize those values everywhere they could surface — Initial state and
Timeline prose, on-demand evidence captions, and delegated batch notes.
Redact or decline to share unsafe frames, and decline outright if the task
requires exposing sensitive content. This rule applies at every point
frames or captions are produced or attached; the rest of this document
refers back to it by name rather than restating it. (The report template
in frame-report-format.md carries its own short reminder of this rule for
when the reference is read in isolation.)

## Report Format (mandatory)

Every answer that analyzes a video uses the four-section report from
[frame-report-format.md](references/frame-report-format.md), in this
order:

`### 🎬 Recording summary` → `### 🖼️ Initial state` → `### ▶️ Timeline` →
`### ⚠️ Analysis notes`

When emitting this report, begin your reply directly with
`### 🎬 Recording summary`. Do not output any preamble, plan, or
reasoning recap (for example "Now I have enough information to write
the report") before the first heading.

This format does not yield to phrasing in the user's request. When the user
asks for "a numbered list", "a description", or "the steps", satisfy that
request inside the template: the ▶️ Timeline is the numbered list of steps,
and static context belongs under 🖼️ Initial state — do not flatten the whole
answer into one undifferentiated list. Skip the template only when there is
nothing to analyze: a still thumbnail or an extraction error.

Timeline entries are deterministic and label-first. Each step must use the
compact grammar from `frame-report-format.md`: a numbered item, a short
bold change label, a backticked approximate time range, then the change
description. Do not improvise time-first, prose-heading, or
`<label> (~t=...)` variants.

## Requirements

The extraction helper needs these on the host running it:

- `python3` (Python 3.9 or newer; the scripts are stdlib-only, no pip
  installs).
- `ffmpeg` and `ffprobe` on `PATH`.

If `ffmpeg`/`ffprobe` are missing, install with the command matching the
running platform, then retry:

| Platform      | Install command                                                                                          |
| ------------- | -------------------------------------------------------------------------------------------------------- |
| macOS         | `brew install ffmpeg`                                                                                    |
| Debian/Ubuntu | `sudo apt-get update && sudo apt-get install -y ffmpeg`                                                  |
| Alpine        | `apk add ffmpeg`                                                                                         |
| Fedora        | `sudo dnf install ffmpeg-free`                                                                           |
| Arch          | `sudo pacman -S ffmpeg`                                                                                  |
| Windows       | `winget install --id Gyan.FFmpeg` or `choco install ffmpeg` (then restart the shell so `PATH` refreshes) |
| Other Linux   | use the distro package manager's `ffmpeg` package                                                        |

The helper's `MISSING_TOOL` error message lists these install commands — run
the one matching the host. If installation is impossible (no network access
or no permission to install), report that extraction could not run — do not
describe a single frame as if it were the whole recording.

## Workflow

1. **Locate the original video file.**
   - Check attached file paths, referenced paths, and relevant workspace
     files for a real video (`.mp4`, `.mov`, `.webm`, `.mkv`, `.m4v`,
     `.mpeg`, `.mpg`).
   - If the only available asset is a PNG/JPEG thumbnail, stop and say the
     recording cannot be reconstructed from a still preview. Ask for the
     original video file.
   - Do not infer motion from a static preview.
   - If the source is a `.gif` or animated WebP/APNG file, stop and say
     this video workflow cannot analyze animated image containers. Ask for
     animated-image extraction tooling or a video container version.

2. **Extract frames.**
   Run the helper against the original video. `<skill-dir>` is the
   directory containing this SKILL.md — use its full path, since your
   working directory is usually elsewhere. The script uses only Python's
   standard library, plus `ffmpeg`/`ffprobe` on `PATH` for media
   extraction.

   ```bash
   python3 <skill-dir>/scripts/extract_video_frames.py <input.mp4>
   ```

   Useful options:

   ```bash
   python3 <skill-dir>/scripts/extract_video_frames.py <input.mp4> --max-frames 40 --max-width 960
   python3 <skill-dir>/scripts/extract_video_frames.py <input.mov> --all-changed
   python3 <skill-dir>/scripts/extract_video_frames.py <input.mp4> --scene-threshold 0.08
   python3 <skill-dir>/scripts/extract_video_frames.py <input.mp4> --start 90 --duration 30
   python3 <skill-dir>/scripts/extract_video_frames.py <input.mp4> --out-dir /tmp/video-frames --no-sheet
   ```

   The helper hashes every decoded frame, so in screen recordings any
   visible change (a typed character, a cursor move, a click feedback
   state) counts as a change. When all changed frames fit the
   `--max-frames` budget (default 24), nothing is sampled away; otherwise
   the budget is spread across time.

3. **Handle long videos.**
   - Every analysis pass decodes the full window. The helper refuses
     windows above ~20,000 decoded frames with error code
     `VIDEO_TOO_LONG`; rerun with `--start <seconds> --duration <seconds>`.
     A window that starts at or past the end of the source, or one
     shorter than the source's frame interval, fails with `EMPTY_WINDOW`
     — pick a start inside `durationSec` and a duration covering at
     least one frame.
   - `VIDEO_TOO_LARGE`, `VIDEO_TOO_LONG`, and `EMPTY_WINDOW` error results
     all include top-level `durationSec` and `fps` when known (the probe
     that discovers them already succeeded before any of the three errors
     fire). For `VIDEO_TOO_LONG` and `EMPTY_WINDOW`, size the rerun
     directly from the error JSON without re-probing: pick `--start`
     inside `durationSec`, and keep `--duration` at or below the frame cap
     divided by `fps` (~20,000 / `fps` seconds) so the new window itself
     does not exceed the cap.
   - `VIDEO_TOO_LARGE` fires on the source's pixel-area alone, before and
     independent of any `--start`/`--duration` window — no windowed rerun
     can succeed. Do not retry with a smaller window; ask the user for a
     downscaled or re-encoded export, or report the resolution limit.
   - For long recordings, do a coarse pass first (whole video or large
     windows), then zoom into the segment that matters with a narrow
     `--start`/`--duration` window plus `--all-changed`.
   - `window` in the JSON echoes the analyzed range; `sampled[].t` stays
     absolute (source time), so timestamps from different windows can be
     compared directly.

4. **Handle helper output.**
   - If `error` is present, report the limitation and describe only what
     is available, labeled as such.
   - If `error.code` is `NO_VIDEO_STREAM`, the file has no video (e.g.
     audio-only); say so.
   - If `error.code` is `STILL_IMAGE`, the source is a still image or
     animated-image container, not a video container. Do not present it as
     a recording; use static-image or animated-image handling instead.
   - Camera footage: when `changedFrameCount` is close to `frameCount`,
     every frame differs (continuous motion or sensor noise). Treat
     `droppedChangeCount` as coverage information, not as missing discrete
     steps — `--all-changed` will not enumerate meaningful "actions"
     there.
   - Screen recordings: if `droppedChangeCount` is `0`, every visual
     change is in `sampled[]` — describe the actions directly; do not
     hedge about unseen intermediate frames.
   - If `droppedChangeCount > 0` and the task depends on every step (typed
     input, exact click moments, animation debugging), rerun with
     `--all-changed` (windowed if needed) before answering. Otherwise
     state the gap in Analysis notes.
   - If `audio.present` is `true`, note in Analysis notes that the audio
     track was not analyzed. Do not invent narration, sounds, or speech.
   - If `sheets` is non-empty, read the contact sheets first, in order.
     Each sheet entry names the global tile numbers it shows
     (`"tiles": "13-24"`), row-major (left-to-right, then
     top-to-bottom).
   - Sheet tiles are downscaled overviews and are too coarse to read text
     reliably. Before naming any product/app, page or slide title, menu
     item, or typed input, open the relevant full-size PNG(s) at `outDir` +
     `sampled[].file` and read the text there — do not transcribe a name
     or label from a contact-sheet tile. If the text is still unreadable
     at full size, keep the wording generic rather than guessing. For
     typed-input sequences, inspect the final full-size frame of the
     sequence; `changeScore` marks the biggest transitions, but small-score
     frames often hold the decisive typed-input delta.
   - `labeled` is often `false` — many ffmpeg builds (including current
     Homebrew) lack the `drawtext` filter. This is normal, not a failure,
     and should never appear in the user-facing report.
   - The `note` field is pre-written Analysis notes material. Use relevant
     coverage, window, and audio context; do not copy sheet-labeling or
     `drawtext` details into the user-facing report.

5. **Optionally delegate large visual reads.**
   Keep the contact-sheet workflow as the default for ordinary runs.
   Consider read-only sub-agent batches only when visual context pressure
   is real:

   - `sampled[]` has more than about 48 frames, or `sheets[]` has more
     than 4 contact sheets.
   - `--all-changed` produces many sampled frames.
   - The default pass looks small but `droppedChangeCount > 0` and the
     task needs every step, forcing an `--all-changed` or windowed rerun.
   - A whole-video `--all-changed` pass hits the 200-frame cap; split into
     windows and treat the aggregate windowed result as the large frame
     set.
   - The user explicitly asks for high-detail analysis of a long or dense
     recording.

   For delegated reads, create batches of 8-10 full-size PNGs from the
   helper JSON using `outDir` + `sampled[].file`. Give each read-only
   sub-agent the frame path, `sampled[].t`, `sampled[].tile`, and
   `changeScore`; ask it to write text-only notes with visible text,
   action delta, uncertainty, and whether Sensitive content rule material
   is present.

   Treat batch notes as advisory visual observations. The helper JSON
   remains the source of truth for timestamps, tile/file mapping,
   coverage, windows, and Analysis notes. The main agent still owns the
   final timeline, maps each claim back to `sampled[].tile` and
   `sampled[].file`, and directly inspects candidate PNGs before attaching
   evidence or exposing sensitive content.

6. **Anchor claims to tiles (internal).**
   While reading sheets, map each timeline claim to tile numbers from
   `sampled[].tile` and timestamps from `sampled[].t`. This is for
   self-check only — do not emit tile numbers or `— evidence: tiles …`
   suffixes in the user-facing report.

7. **Retain extraction context.**
   Treat the full helper JSON, the source file path, and the exact helper
   options used as session state after extraction, including `--start`,
   `--duration`, `--all-changed`, `--max-frames`, `--max-width`,
   `--scene-threshold`, `--out-dir`, and `--sheet`/`--no-sheet` when
   present. The helper writes PNGs to a local directory (default: OS tmp
   via `mkdtemp`; override with `--out-dir`). These artifacts support
   on-demand proof in a follow-up without re-running unless files were
   cleaned up or the user points at a different source file. Re-running
   the helper against the same `--out-dir` pre-cleans matching PNGs
   before writing — see Helper Contract's `outDir` bullet.

   For sensitive recordings, use OS tmp or a workspace-scoped `--out-dir`
   only when the target is an explicitly gitignored scratch directory.
   Before attaching frames or finishing cleanup, check that generated
   evidence files are not staged or tracked; apply the Sensitive content
   rule. Cleanup of retained PNGs is actioned in On-demand evidence
   step 6.

8. **Describe deltas, not frames.**
   Describe the starting view once, as a bulleted Initial state section
   (layout, visible sidebars/panels, active tab, where focus or the caret
   sits). Then list only changes in the timeline, starting at the first
   observed change. Compare adjacent sampled frames and explain what
   changed. Do not produce a tile-by-tile inventory. Apply the Sensitive
   content rule to the Initial state and Timeline prose.
   Use the template in
   [frame-report-format.md](references/frame-report-format.md). For the
   final video report, the first visible line must be exactly
   `### 🎬 Recording summary`; delete any status or setup sentence such
   as "Now...", "Perfect!", "Based on the frames...", or "Let me create
   the report:" before sending. Before emitting any app/site/domain,
   page or slide title, menu item, or typed input name, confirm it came
   from a relevant full-size PNG; if not, replace it with generic
   wording rather than guessing. Keep Initial state and Analysis notes
   as `-` bulleted lists, not paragraphs. Timeline rows must match
   ``**<label>** (`~t=<start>–<end>s`): <what changed>`` — use a colon
   after the backticked range, not an em dash. Then run the reference
   file's determinism checklist: all four headings (🎬 🖼️ ▶️ ⚠️),
   compact label-first timeline rows, bulleted Analysis notes, and the
   verbatim 🔍 evidence footnote when applicable (see frame-report-format
   Writing Rules for when to skip).

## On-demand evidence

When the user asks for proof, evidence, frames, or "show your work"
(including referencing a specific timeline step):

1. **Locate artifacts** — use the retained `outDir` from the prior
   extraction JSON. If missing or files were cleaned up, re-run the helper
   against the same source file with the same retained extraction options
   (`--start`, `--duration`, `--all-changed`, `--max-frames`,
   `--max-width`, `--scene-threshold`, `--out-dir`, `--sheet`/`--no-sheet`,
   etc.) so timestamps, tile numbers, and sampled frames still match the
   original analysis.
2. **Map the request** — match by timestamp (`t=…`), step description, or
   the tile range used internally while analyzing.
3. **Review safety** — apply the Sensitive content rule to candidate PNGs
   before attaching them.
4. **Attach minimally** — prefer full-size PNGs at `outDir` +
   `sampled[].file` for the 1–3 frames that bracket the change
   (before/after), not every sheet. Use a contact-sheet page only when the
   user wants an overview of many tiles.
5. **Caption briefly** — one line per image: timestamp, tile number, what
   it shows. Tie back to the timeline step in plain language; captions
   stay subject to the Sensitive content rule.
6. **Clean up when done** — delete retained PNGs once the evidence
   workflow is complete and follow-up proof is no longer needed.
7. **Do not** re-dump the full default report or re-attach all sheets
   unless explicitly asked.

Trigger phrases: "proof", "evidence", "show frames", "show your work",
"which frame", "how do you know".

## Anti-Patterns

- Do not describe a video from a single visible frame when the task
  depends on time or motion.
- Do not claim to understand the recording if only a still thumbnail is
  available.
- Do not describe frame contents tile-by-tile; describe what changed
  between tiles.
- Do not pad the timeline with static-state descriptions; state setup once
  in Initial state.
- Do not log a panel, sidebar, chat, or element already present in the
  first frame as a timeline action — it is Initial state context. Add it
  to the timeline only if it opens, closes, or visibly changes on screen.
- Do not abandon the report template because the user asked for a list or
  description — render their request inside the template's sections.
- Do not invent transitions between sampled frames. If a cause is not
  visible, say between `` `~t=X–Ys` `` (plain "between", backticked
  range).
- Do not describe audio content — the helper never decodes the audio
  track.
- Do not present a windowed analysis as full coverage; state the analyzed
  range when `window` is set.
- Do not append `— evidence: tiles …` suffixes or attach contact sheets in
  the default report.
- The 🔍 evidence footnote is discoverability text only — not evidence
  itself; still attach frames only when the user asks.
- Do not attach all extracted frames when the user only asked about one
  step.
- Do not let delegated batch notes replace helper JSON, tile/file mapping,
  or direct frame review before attaching evidence or revealing sensitive
  content.

## Helper Contract

The helper prints JSON (`version: 2`). File paths in `sheets[]` and
`sampled[]` are relative to `outDir`; times are seconds.

- `source`, `format` — container detected by ffprobe
  (`mov,mp4,m4a,3gp,3g2,mj2` for MP4/MOV, `matroska,webm` for WebM/MKV; an
  image format means the file is a still preview)
- `durationSec` — full file duration, even when a window was analyzed
- `fps` — nominal frame rate of the video stream
- `window` — `{ startSec, durationSec }` of the analyzed range; **omitted**
  (not `null`) for the whole file. `durationSec` itself is `null` (not
  omitted) when the window is open-ended (`--start` given without
  `--duration`) — the `None`-stripping that omits whole-file `window` only
  applies at the top level, not to nested fields
- `frameCount`, `distinctFrameCount`, `changedFrameCount` — decoded /
  unique-by-hash / changed-vs-previous frames in the analyzed window (in
  screen recordings every typed character or cursor move counts as
  changed). `distinctFrameCount`, `changedFrameCount`, and
  `droppedChangeCount` are **omitted** (not present as keys) when
  frame-hashing was unavailable — absence means "unknown coverage", not
  zero. Whole-file passes match hashes to frames by position when both
  passes decode the same frame count, so hashing stays usable even on
  variable-frame-rate sources (e.g. screen recordings) whose hash pass
  emits coarsely quantized timestamps; a windowed pass (`--start`/
  `--duration`) can still fall back to timestamp-tolerance matching, and on
  a VFR source may occasionally report hashing unavailable, if ffprobe and
  ffmpeg disagree on the window's frame count
- `droppedChangeCount` — changed frames missing from `sampled[]`; `0`
  means the sample is complete; omitted when hashing was unavailable (see
  above)
- `audio` — `{ present, codec }`; the track is never analyzed, only
  reported
- `outDir`, `frameSize` — dimensions of all extracted PNGs (capped by
  `--max-width`). Warning: writing to `outDir` deletes any pre-existing
  `frame-NNN.png`, `labeled-NNN.png`, and `contact-sheet*.png` there, so a
  reused `--out-dir` wipes previously retained frames. The helper rejects
  an input path that would be deleted or overwritten by those generated
  output names
- `labeled` — whether tile labels are burned into the sheets
- `note` — plain-language coverage, window, and audio context for the ⚠️
  Analysis notes section
- `sheets[]`: `{ file, tiles, cols, rows }` — paginated at 12 tiles per
  sheet; `tiles` is the global tile-number range shown (e.g. `"13-24"`)
- `sampled[]`: `{ tile, index, t, file, changeScore }` — global tile
  number, frame index relative to the analyzed window, absolute source
  time in seconds, PNG filename, and 0–1 change intensity vs the previous
  frame. `t` comes from the frame timestamp when available; if the media
  omits timestamps, the helper synthesizes approximate monotonically
  increasing times from frame order and duration metadata
- `error`: `{ code, message }` when extraction fails — `code` is one of
  `MISSING_TOOL` (ffmpeg/ffprobe absent), `NOT_FILE` (the input path is
  missing or not a regular file), `OUTPUT_COLLISION` (the input path would
  be deleted or overwritten by generated frame/contact-sheet output names),
  `TIMEOUT` (the subprocess timed out), `USAGE` or `UNKNOWN_OPTION` (bad
  invocation), `NO_VIDEO_STREAM` (no video track), `STILL_IMAGE` (the
  source is a still image or animated-image container, not a video
  container), `VIDEO_TOO_LARGE` (the canvas exceeds the pixel-area cap),
  `VIDEO_TOO_LONG` (window exceeds the decoded-frame cap), `EMPTY_WINDOW`
  (the `--start`/`--duration` window contains no frames), or
  `EXTRACTION_FAILED` (unreadable/corrupt media — including an existing
  file that fails to read due to permissions — a filesystem error on the
  output directory, or any other unexpected internal error). The
  `MISSING_TOOL` message includes platform install commands — run the
  matching one, then retry. `VIDEO_TOO_LARGE`, `VIDEO_TOO_LONG`, and
  `EMPTY_WINDOW` results also carry top-level `durationSec` and `fps` when
  known. Only `VIDEO_TOO_LONG` and `EMPTY_WINDOW` are fixable with a
  rerun — see step 3 for sizing the `--start`/`--duration` window from
  them. `VIDEO_TOO_LARGE` is window-independent (it fires on pixel area
  alone); no rerun helps — ask for a downscaled/re-encoded export or
  report the limit

`--all-changed` extracts every hash-distinct frame (capped at 200) instead
of the `--max-frames` budget. Use it when the task hinges on exact
per-frame detail: debugging animations, catching the frame where a click
landed, or transcribing typed input.

See Requirements for the fallback when ffmpeg cannot be installed.
