# services package
from src.services.script_generator import (
    GeneratedScriptResponse,
    ScriptSegment,
    generate_script,
)
from src.services.unified_tts import (
    UNIFIED_PITCH,
    UNIFIED_SPEAKING_RATE,
    UNIFIED_VOICE_ID,
    UnifiedTTSManager,
)
from src.services.audio_ducking import (
    DEFAULT_DUCK_LEVEL,
    DEFAULT_NORMAL_LEVEL,
    get_bgm_volume_at,
    generate_ducking_volume_timeline,
    generate_ducking_keyframes,
    build_ffmpeg_ducking_filter,
)

__all__ = [
    "GeneratedScriptResponse",
    "ScriptSegment",
    "generate_script",
    "UNIFIED_VOICE_ID",
    "UNIFIED_SPEAKING_RATE",
    "UNIFIED_PITCH",
    "UnifiedTTSManager",
    "DEFAULT_DUCK_LEVEL",
    "DEFAULT_NORMAL_LEVEL",
    "get_bgm_volume_at",
    "generate_ducking_volume_timeline",
    "generate_ducking_keyframes",
    "build_ffmpeg_ducking_filter",
]
