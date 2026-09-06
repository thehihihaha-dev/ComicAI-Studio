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

from src.services.chapter_service import (
    ChapterMetadata,
    PageMetadata,
    PanelMetadata,
    ingest_chapter,
    calculate_panel_visual_score,
)
from src.services.smart_selector import (
    SelectedPanel,
    select_keyframe_panels,
    convert_to_visual_clips,
    MOTION_PRESETS,
)
from src.services.video_renderer import (
    VerticalFrameBuilder,
    VideoRenderer,
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
    "ChapterMetadata",
    "PageMetadata",
    "PanelMetadata",
    "ingest_chapter",
    "calculate_panel_visual_score",
    "SelectedPanel",
    "select_keyframe_panels",
    "convert_to_visual_clips",
    "MOTION_PRESETS",
    "VerticalFrameBuilder",
    "VideoRenderer",
]

