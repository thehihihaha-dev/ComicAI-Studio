"""Day 19 Phase 1: Audio Ducking Engine.

Automatically attenuates Background Music (BGM) volume to 25% during active
narration speech intervals and smoothly fades back up to 100% during pauses.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

logger = logging.getLogger(__name__)

DEFAULT_DUCK_LEVEL = 0.25     # 25% volume during speech
DEFAULT_NORMAL_LEVEL = 1.00   # 100% volume during pauses/silence
DEFAULT_FADE_IN_SEC = 0.30    # Transition duration from 25% -> 100% after speech ends
DEFAULT_FADE_OUT_SEC = 0.10   # Transition duration from 100% -> 25% before speech begins


def get_bgm_volume_at(
    t: float,
    voice_intervals: Sequence[tuple[float, float]],
    duck_level: float = DEFAULT_DUCK_LEVEL,
    normal_level: float = DEFAULT_NORMAL_LEVEL,
    fade_in_sec: float = DEFAULT_FADE_IN_SEC,
    fade_out_sec: float = DEFAULT_FADE_OUT_SEC,
) -> float:
    """Calculates instantaneous BGM volume multiplier at timestamp `t`.

    Args:
        t: Current playback/render timestamp in seconds.
        voice_intervals: List of (start_time, end_time) pairs where speech is active.
        duck_level: Attenuated BGM volume (default 0.25 = 25%).
        normal_level: Baseline BGM volume (default 1.00 = 100%).
        fade_in_sec: Duration to recover to 100% after voice ends.
        fade_out_sec: Duration to lower to 25% leading into voice.

    Returns:
        float: Volume multiplier in range [duck_level, normal_level].
    """
    if not voice_intervals:
        return normal_level

    # 1. Direct check: Is t strictly inside any voice active interval?
    for start, end in voice_intervals:
        if start <= t <= end:
            return duck_level

    # 2. Transition check: calculate minimum volume across all intervals
    min_vol = normal_level

    for start, end in voice_intervals:
        # Before interval (fade-out from normal -> duck)
        if fade_out_sec > 0 and (start - fade_out_sec) <= t < start:
            progress = (start - t) / fade_out_sec  # 1.0 at start-fade_out, 0.0 at start
            vol = duck_level + (normal_level - duck_level) * progress
            if vol < min_vol:
                min_vol = vol

        # After interval (fade-in from duck -> normal)
        elif fade_in_sec > 0 and end < t <= (end + fade_in_sec):
            progress = (t - end) / fade_in_sec     # 0.0 at end, 1.0 at end+fade_in
            vol = duck_level + (normal_level - duck_level) * progress
            if vol < min_vol:
                min_vol = vol

    return round(float(min_vol), 4)


def generate_ducking_volume_timeline(
    voice_intervals: Sequence[tuple[float, float]],
    total_duration: float,
    sample_rate_hz: float = 10.0,
    duck_level: float = DEFAULT_DUCK_LEVEL,
    normal_level: float = DEFAULT_NORMAL_LEVEL,
    fade_in_sec: float = DEFAULT_FADE_IN_SEC,
    fade_out_sec: float = DEFAULT_FADE_OUT_SEC,
) -> list[dict[str, float]]:
    """Generates a discrete sequence of timestamp-volume pairs for timeline visualization."""
    timeline: list[dict[str, float]] = []
    if total_duration <= 0:
        return timeline

    step = 1.0 / sample_rate_hz
    curr_t = 0.0

    while curr_t <= total_duration:
        vol = get_bgm_volume_at(
            t=curr_t,
            voice_intervals=voice_intervals,
            duck_level=duck_level,
            normal_level=normal_level,
            fade_in_sec=fade_in_sec,
            fade_out_sec=fade_out_sec,
        )
        timeline.append({"time": round(curr_t, 3), "volume": vol})
        curr_t += step

    return timeline


def generate_ducking_keyframes(
    voice_intervals: Sequence[tuple[float, float]],
    total_duration: float,
    duck_level: float = DEFAULT_DUCK_LEVEL,
    normal_level: float = DEFAULT_NORMAL_LEVEL,
    fade_in_sec: float = DEFAULT_FADE_IN_SEC,
    fade_out_sec: float = DEFAULT_FADE_OUT_SEC,
) -> list[dict[str, Any]]:
    """Generates boundary keyframes representing the ducking volume automation curve.

    Suitable for Web Editor automation points and FFmpeg volume filters.
    """
    keyframes: list[dict[str, Any]] = []

    # Sort intervals
    sorted_intervals = sorted(voice_intervals, key=lambda x: x[0])
    if not sorted_intervals:
        keyframes.append({"time": 0.0, "volume": normal_level})
        keyframes.append({"time": total_duration, "volume": normal_level})
        return keyframes

    last_t = 0.0
    for start, end in sorted_intervals:
        duck_start = max(last_t, start - fade_out_sec)

        # Before ducking starts: normal volume
        if duck_start > last_t:
            keyframes.append({"time": round(last_t, 3), "volume": normal_level})
            keyframes.append({"time": round(duck_start, 3), "volume": normal_level})

        # At start of voice: duck level reached
        keyframes.append({"time": round(start, 3), "volume": duck_level})

        # At end of voice: still at duck level
        keyframes.append({"time": round(end, 3), "volume": duck_level})

        # Recovery point: normal volume restored
        fade_end = min(total_duration, end + fade_in_sec)
        keyframes.append({"time": round(fade_end, 3), "volume": normal_level})
        last_t = fade_end

    if last_t < total_duration:
        keyframes.append({"time": round(total_duration, 3), "volume": normal_level})

    return keyframes


def build_ffmpeg_ducking_filter(
    voice_intervals: Sequence[tuple[float, float]],
    duck_level: float = DEFAULT_DUCK_LEVEL,
    normal_level: float = DEFAULT_NORMAL_LEVEL,
    fade_in_sec: float = DEFAULT_FADE_IN_SEC,
    fade_out_sec: float = DEFAULT_FADE_OUT_SEC,
) -> str:
    """Builds an FFmpeg volume filter expression using piecewise conditions.

    Example output:
        volume='if(between(t,1.0,4.0),0.25,if(between(t,6.0,9.0),0.25,1.0))':eval=frame
    """
    if not voice_intervals:
        return f"volume={normal_level}"

    sorted_intervals = sorted(voice_intervals, key=lambda x: x[0])
    conditions = []

    for start, end in sorted_intervals:
        conditions.append(f"between(t,{start:.3f},{end:.3f})")

    # Combine with OR logic
    combined_speech = "+".join(conditions)
    expr = f"if(gte({combined_speech},1),{duck_level:.2f},{normal_level:.2f})"
    return f"volume='{expr}':eval=frame"

