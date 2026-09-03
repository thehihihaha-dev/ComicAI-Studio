"""Day 16 Phase 2: Pluggable TTS Synthesis & Timeline Alignment Engine.

Provides:
1. VoiceProfile: Configuration dataclass for voice ID, gender, rate, and pitch.
2. VoiceSynthesisEngine: Voice mapping profiles per SpeakerRole with deterministic
   duration computation and surrogate audio artifact generation.
3. TimelineAligner: Computes sequential timeline alignment per page (start_ms, end_ms,
   inter-bubble and inter-panel pauses) ensuring zero speech overlaps.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from src.pipeline.research.day16_dialogue import SpeakerRole


@dataclass(frozen=True)
class VoiceProfile:
    voice_id: str
    gender: str
    rate: str = "+0%"
    pitch: str = "+0Hz"


class VoiceSynthesisEngine:
    """Pluggable TTS synthesis engine with voice mapping and deterministic duration modeling."""

    def __init__(self, voice_registry: dict[SpeakerRole, VoiceProfile] | None = None) -> None:
        self.voice_registry = voice_registry or {
            SpeakerRole.KAZU: VoiceProfile(
                voice_id="vi-VN-NamMinhNeural",
                gender="male",
                rate="+15%",
                pitch="+0Hz",
            ),
            SpeakerRole.RIN: VoiceProfile(
                voice_id="vi-VN-HoaiMyNeural",
                gender="female",
                rate="+20%",
                pitch="+10Hz",
            ),
            SpeakerRole.NARRATOR: VoiceProfile(
                voice_id="vi-VN-NamMinhNeural",
                gender="male",
                rate="+15%",
                pitch="+0Hz",
            ),
            SpeakerRole.PRIEST: VoiceProfile(
                voice_id="vi-VN-NamMinhNeural",
                gender="male",
                rate="+5%",
                pitch="-2Hz",
            ),
            SpeakerRole.UNKNOWN: VoiceProfile(
                voice_id="vi-VN-HoaiMyNeural",
                gender="female",
                rate="+0%",
                pitch="+0Hz",
            ),
        }

    def get_profile(self, speaker_role: str | SpeakerRole) -> VoiceProfile:
        """Retrieve VoiceProfile for a given speaker role with fallback."""
        if isinstance(speaker_role, str):
            try:
                role = SpeakerRole(speaker_role)
            except ValueError:
                role = SpeakerRole.UNKNOWN
        else:
            role = speaker_role
        return self.voice_registry.get(role, self.voice_registry[SpeakerRole.UNKNOWN])

    def estimate_duration_ms(self, text: str, speaking_rate_wpm: int = 155) -> int:
        """Deterministic speech duration modeling with syllable pacing and punctuation pauses."""
        if not text or not text.strip():
            return 600

        clean = text.strip()
        words = clean.split()
        num_words = max(1, len(words))

        # Base word pacing: 60,000 ms / WPM
        ms_per_word = 60000.0 / float(speaking_rate_wpm)
        base_duration = float(num_words) * ms_per_word

        # Character length adjustment (ensure at least 50ms per character)
        char_duration = float(len(clean)) * 50.0
        est_duration = max(base_duration, char_duration)

        # Punctuation pause bonuses
        pause_bonus = 0.0
        pause_bonus += len(re.findall(r"[,;]", clean)) * 200.0
        pause_bonus += len(re.findall(r"(?:\.\.\.)", clean)) * 500.0
        pause_bonus += len(re.findall(r"(?<!\.)\.(?!\.)", clean)) * 350.0
        pause_bonus += len(re.findall(r"[!?]", clean)) * 400.0

        total_ms = int(round(est_duration + pause_bonus))
        return max(600, total_ms)

    def synthesize_surrogate_audio(self, dialogue: dict[str, Any]) -> dict[str, Any]:
        """Generate deterministic audio metadata and surrogate payload digest."""
        did = dialogue.get("dialogue_id", "")
        role = dialogue.get("speaker_label", SpeakerRole.UNKNOWN.value)
        text = dialogue.get("tts_ready_text", dialogue.get("cleaned_text", ""))

        profile = self.get_profile(role)
        duration_ms = self.estimate_duration_ms(text)

        audio_id = f"AUD_{did}"
        # Estimate PCM 16-bit 24kHz mono byte size (48 bytes per ms)
        pcm_bytes_estimate = duration_ms * 48

        payload_sig = f"{audio_id}:{profile.voice_id}:{duration_ms}:{text}"
        payload_sha256 = hashlib.sha256(payload_sig.encode("utf-8")).hexdigest()

        return {
            "audio_id": audio_id,
            "voice_id": profile.voice_id,
            "gender": profile.gender,
            "speaking_rate": profile.rate,
            "pitch": profile.pitch,
            "duration_ms": duration_ms,
            "audio_format": "wav",
            "sample_rate_hz": 24000,
            "channels": 1,
            "bit_depth": 16,
            "pcm_bytes_estimate": pcm_bytes_estimate,
            "audio_payload_sha256": payload_sha256,
        }


class TimelineAligner:
    """Computes sequential timeline alignment per page ensuring zero speech overlap."""

    def __init__(
        self,
        pause_between_bubbles_ms: int = 150,
        pause_between_panels_ms: int = 300,
    ) -> None:
        self.pause_between_bubbles_ms = pause_between_bubbles_ms
        self.pause_between_panels_ms = pause_between_panels_ms

    def align_page_dialogues(
        self,
        dialogues: Sequence[dict[str, Any]],
        synthesis_engine: VoiceSynthesisEngine | None = None,
    ) -> list[dict[str, Any]]:
        """Align dialogues on a page monotonically from 0 ms."""
        engine = synthesis_engine or VoiceSynthesisEngine()
        aligned: list[dict[str, Any]] = []

        current_time_ms = 0
        prev_panel_id: str | None = None

        for index, item in enumerate(dialogues):
            entry = dict(item)
            panel_id = entry.get("panel_id", "")

            # Inter-bubble or inter-panel pause
            if index > 0:
                if panel_id == prev_panel_id:
                    pause = self.pause_between_bubbles_ms
                else:
                    pause = self.pause_between_panels_ms
                current_time_ms += pause

            # Compute audio metadata and duration
            audio_meta = engine.synthesize_surrogate_audio(entry)
            duration_ms = audio_meta["duration_ms"]

            start_ms = current_time_ms
            end_ms = start_ms + duration_ms
            current_time_ms = end_ms
            prev_panel_id = panel_id

            entry["audio_id"] = audio_meta["audio_id"]
            entry["voice_id"] = audio_meta["voice_id"]
            entry["duration_ms"] = duration_ms
            entry["start_ms"] = start_ms
            entry["end_ms"] = end_ms
            entry["timestamps"] = {
                "start_ms": start_ms,
                "end_ms": end_ms,
            }
            entry["audio_metadata"] = audio_meta

            aligned.append(entry)

        return aligned

