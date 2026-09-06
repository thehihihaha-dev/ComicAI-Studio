"""Day 19 Phase 1: Unified Neural TTS Engine.

Enforces a single narrator voice: `vi-VN-NamMinhNeural` at `rate="+12%"`, `pitch="0%"`
across all video review segments with frame-accurate pause stitching.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

import mutagen.mp3

try:
    from src.pipeline.research.day17_live_tts import generate_mp3_silence
    from src.services.script_generator import GeneratedScriptResponse, ScriptSegment
except ModuleNotFoundError:
    from backend.src.pipeline.research.day17_live_tts import generate_mp3_silence
    from backend.src.services.script_generator import GeneratedScriptResponse, ScriptSegment

logger = logging.getLogger(__name__)

# Mandatory Single-Voice Specifications
UNIFIED_VOICE_ID = "vi-VN-NamMinhNeural"
UNIFIED_SPEAKING_RATE = "+12%"
UNIFIED_PITCH = "0%"
DEFAULT_INTER_SEGMENT_PAUSE_SEC = 0.30


class UnifiedTTSManager:
    """Manages speech synthesis for script segments strictly adhering to unified voice specifications."""

    def __init__(
        self,
        voice_id: str = UNIFIED_VOICE_ID,
        speaking_rate: str = UNIFIED_SPEAKING_RATE,
        pitch: str = UNIFIED_PITCH,
        offline_fallback: bool = True,
    ) -> None:
        self.voice_id = voice_id
        self.speaking_rate = speaking_rate
        self.pitch = pitch
        self.offline_fallback = offline_fallback

    async def synthesize_segment(
        self,
        text: str,
        output_path: Path,
        fallback_duration_sec: float = 2.0,
    ) -> float:
        """Synthesize a single script segment to MP3.

        Returns:
            duration_seconds: Measured physical audio length.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice_id,
                rate=self.speaking_rate,
                pitch=self.pitch,
            )
            await communicate.save(str(output_path))
            audio_info = mutagen.mp3.MP3(str(output_path)).info
            return float(audio_info.length)
        except Exception as exc:
            if not self.offline_fallback:
                raise exc
            logger.info(
                f"Edge TTS synthesis unavailable ({exc}), writing deterministic surrogate silence for: {output_path.name}"
            )
            fallback_ms = int(round(fallback_duration_sec * 1000.0))
            silence_bytes = generate_mp3_silence(fallback_ms)
            output_path.write_bytes(silence_bytes)
            audio_info = mutagen.mp3.MP3(str(output_path)).info
            return float(audio_info.length)

    async def synthesize_script(
        self,
        script: GeneratedScriptResponse,
        output_dir: Path,
        pause_between_sec: float = DEFAULT_INTER_SEGMENT_PAUSE_SEC,
    ) -> list[dict[str, Any]]:
        """Synthesizes all segments from a GeneratedScriptResponse and aligns timestamps.

        Returns:
            List of synthesized segment metadata with exact start_time and end_time.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, Any]] = []

        current_time = 0.0

        for idx, segment in enumerate(script.segments):
            safe_name = f"{segment.id}_{idx+1:02d}.mp3"
            clip_path = output_dir / safe_name

            dur_sec = await self.synthesize_segment(
                text=segment.text,
                output_path=clip_path,
                fallback_duration_sec=segment.estimated_duration,
            )

            start_t = round(current_time, 3)
            end_t = round(current_time + dur_sec, 3)
            current_time = end_t + pause_between_sec

            results.append({
                "segment_id": segment.id,
                "section_type": segment.section_type,
                "text": segment.text,
                "voice_id": self.voice_id,
                "speaking_rate": self.speaking_rate,
                "pitch": self.pitch,
                "suggested_effect": segment.suggested_effect,
                "file_path": str(clip_path),
                "duration": round(dur_sec, 3),
                "start_time": start_t,
                "end_time": end_t,
            })

        return results

    def stitch_speech_track(
        self,
        synthesized_segments: Sequence[dict[str, Any]],
        output_file: Path,
        pause_between_sec: float = DEFAULT_INTER_SEGMENT_PAUSE_SEC,
    ) -> float:
        """Stitches all segment MP3 files into a single unified continuous narration audio track.

        Returns:
            duration_seconds: Total stitched audio file duration.
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)
        stitched_data = bytearray()
        pause_ms = int(round(pause_between_sec * 1000.0))

        for idx, seg in enumerate(synthesized_segments):
            clip_file = Path(seg["file_path"])
            if not clip_file.is_file():
                raise FileNotFoundError(f"Missing segment audio file: {clip_file}")

            # Insert pause between segments
            if idx > 0 and pause_ms > 0:
                stitched_data.extend(generate_mp3_silence(pause_ms))

            stitched_data.extend(clip_file.read_bytes())

        output_file.write_bytes(bytes(stitched_data))
        audio_info = mutagen.mp3.MP3(str(output_file)).info
        return float(audio_info.length)

