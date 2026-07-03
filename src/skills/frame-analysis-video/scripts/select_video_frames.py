"""Select representative changed frames from a video."""

from __future__ import annotations

from math import floor, isfinite
from typing import Any

# Keep this selector self-contained so the video skill can be published and
# installed independently.
DEFAULT_MAX_FRAMES = 24
DEFAULT_MIN_FRAMES = 3
DEFAULT_SCENE_THRESHOLD = 0.08


def select_video_frames(
    frames: list[dict[str, Any]], options: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    options = options or {}
    normalized_frames = normalize_frames(frames)
    if len(normalized_frames) <= 1:
        return normalized_frames

    max_frames = _clamp_integer(
        options.get("maxFrames"),
        2,
        len(normalized_frames),
        DEFAULT_MAX_FRAMES,
    )
    min_frames = min(
        max_frames,
        _clamp_integer(options.get("minFrames"), 1, max_frames, DEFAULT_MIN_FRAMES),
    )
    scene_threshold = (
        options["sceneThreshold"]
        if _is_finite_number(options.get("sceneThreshold"))
        and options["sceneThreshold"] >= 0
        else DEFAULT_SCENE_THRESHOLD
    )

    first_frame = normalized_frames[0]
    last_frame = normalized_frames[-1]

    changed_frames = []
    for frame in normalized_frames:
        if frame["index"] in {first_frame["index"], last_frame["index"]}:
            continue
        if isinstance(frame.get("hashChanged"), bool):
            if frame["hashChanged"] is True:
                changed_frames.append(frame)
            continue
        if frame["changeScore"] >= scene_threshold:
            changed_frames.append(frame)

    selected_by_index: dict[int, dict[str, Any]] = {}
    _add_frame(selected_by_index, first_frame)
    _add_frame(selected_by_index, last_frame)

    if len(selected_by_index) + len(changed_frames) <= max_frames:
        for frame in changed_frames:
            _add_frame(selected_by_index, frame)
    else:
        _add_coverage_frames(
            selected_by_index=selected_by_index,
            candidates=changed_frames,
            max_frames=max_frames,
            first_frame=first_frame,
            last_frame=last_frame,
        )

    if len(selected_by_index) < min_frames:
        _fill_evenly_spaced_frames(
            frames=normalized_frames,
            selected_by_index=selected_by_index,
            target_count=min_frames,
            excluded_indexes=set(),
        )

    return sorted(selected_by_index.values(), key=_time_key)


def normalize_frames(frames: Any) -> list[dict[str, Any]]:
    if not isinstance(frames, list):
        return []

    normalized = []
    for position, frame in enumerate(frames):
        frame = frame if isinstance(frame, dict) else {}
        index = frame.get("index") if isinstance(frame.get("index"), int) else position
        timestamp_ms = (
            frame["timestampMs"]
            if _is_finite_number(frame.get("timestampMs"))
            else position
        )
        change_score = (
            frame["changeScore"] if _is_finite_number(frame.get("changeScore")) else 0
        )
        normalized_frame = {
            **frame,
            "index": index,
            "timestampMs": timestamp_ms,
            "changeScore": change_score,
        }
        normalized.append(normalized_frame)

    return sorted(normalized, key=_time_key)


def _clamp_integer(value: Any, min_value: int, max_value: int, fallback: int) -> int:
    if not _is_finite_number(value):
        return min(max_value, max(min_value, fallback))
    return min(max_value, max(min_value, floor(value)))


def _add_frame(
    selected_by_index: dict[int, dict[str, Any]], frame: dict[str, Any] | None
) -> None:
    if frame is not None:
        selected_by_index[frame["index"]] = frame


def _add_coverage_frames(
    *,
    selected_by_index: dict[int, dict[str, Any]],
    candidates: list[dict[str, Any]],
    max_frames: int,
    first_frame: dict[str, Any],
    last_frame: dict[str, Any],
) -> None:
    budget = max_frames - len(selected_by_index)
    if budget <= 0 or not candidates:
        return

    span_start = first_frame["timestampMs"]
    span = max(1, last_frame["timestampMs"] - span_start)
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(budget)]
    for candidate in candidates:
        position = floor(((candidate["timestampMs"] - span_start) / span) * budget)
        buckets[min(budget - 1, max(0, position))].append(candidate)

    leftovers = []
    for bucket in buckets:
        if not bucket:
            continue
        bucket.sort(key=_change_key)
        _add_frame(selected_by_index, bucket[0])
        leftovers.extend(bucket[1:])

    leftovers.sort(key=_change_key)
    for frame in leftovers:
        if len(selected_by_index) >= max_frames:
            return
        _add_frame(selected_by_index, frame)


def _fill_evenly_spaced_frames(
    *,
    frames: list[dict[str, Any]],
    selected_by_index: dict[int, dict[str, Any]],
    target_count: int,
    excluded_indexes: set[int],
) -> None:
    if len(selected_by_index) >= target_count:
        return

    candidates = [frame for frame in frames if frame["index"] not in excluded_indexes]
    for slot in range(target_count):
        if len(selected_by_index) >= target_count:
            return
        position = (
            0
            if target_count == 1
            else round((slot * (len(candidates) - 1)) / (target_count - 1))
        )
        _add_frame(selected_by_index, candidates[position])

    for frame in candidates:
        if len(selected_by_index) >= target_count:
            return
        _add_frame(selected_by_index, frame)


def _time_key(frame: dict[str, Any]) -> tuple[float, int]:
    return (frame["timestampMs"], frame["index"])


def _change_key(frame: dict[str, Any]) -> tuple[float, int]:
    return (-frame["changeScore"], frame["index"])


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
