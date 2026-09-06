"""Day 19 Phase 1: AI Script Engine for Comic/Manga Short Video Reviews.

Transforms raw OCR dialogues into a unified narration review script with
multiple narrative styles (dramatic, humorous, romantic) and automated fallback.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Sequence

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SUPPORTED_STYLES = ("dramatic", "humorous", "romantic")
SECTION_TYPES = ("hook", "body", "call_to_action")
SUGGESTED_EFFECTS = ("punch_zoom", "zoom_in", "pan_down", "zoom_out", "blur_glow", "static_focus")

# Approximate Vietnamese narration rate: ~3.2 words per second (190 WPM)
WORDS_PER_SECOND = 3.2


class ScriptSegment(BaseModel):
    id: str = Field(..., description="Unique segment identifier")
    section_type: str = Field(..., description="'hook' (0-3s), 'body', or 'call_to_action'")
    text: str = Field(..., description="Narrator script review text")
    estimated_duration: float = Field(..., description="Estimated speech duration in seconds")
    suggested_effect: str = Field(..., description="Visual effect: zoom_in, punch_zoom, pan_down, etc.")


class GeneratedScriptResponse(BaseModel):
    project_id: str = Field(..., description="Associated project ID")
    story_style: str = Field(..., description="Style used: dramatic, humorous, or romantic")
    total_duration: float = Field(..., description="Sum of segment durations in seconds")
    segments: list[ScriptSegment] = Field(..., description="Ordered list of script segments")


STYLE_SYSTEM_PROMPTS = {
    "dramatic": (
        "Bạn là một biên kịch review truyện tranh kịch tính, gay cấn. "
        "Phong cách: Câu từ dồn dập, nhịp nhanh, ngôn từ sắc bén, đẩy cao mâu thuẫn và kịch tính. "
        "Tập trung vào sự bất ngờ, bí ẩn và tình thế ngặt nghèo của nhân vật."
    ),
    "humorous": (
        "Bạn là một bình luận viên review truyện tranh hài hước, dí dỏm, châm biếm sâu cay. "
        "Phong cách: Dùng từ lóng hài hước, cà khịa tình huống ngớ ngẩn, biểu cảm khó đỡ của nhân vật, "
        "khiến người xem cười nghiêng ngả nhưng vẫn hiểu trọn vẹn cốt truyện."
    ),
    "romantic": (
        "Bạn là một người kể chuyện ngôn tình lãng mạn, tinh tế và ấm áp. "
        "Phong cách: Lời bình nhẹ nhàng, sâu lắng, tập trung vào rung động con tim, "
        "ánh mắt, sự quan tâm âm thầm và cảm xúc ngọt ngào giữa hai nhân vật."
    ),
}

FALLBACK_TEMPLATES = {
    "dramatic": {
        "hook": "Cứ ngỡ là hôn lễ trong mơ, ai ngờ lại là cái bẫy trí mạng!",
        "body_1": "Ngay tại thánh đường trang nghiêm, sự thật kinh hoàng đã chính thức bị vạch trần.",
        "body_2": "Ánh mắt lạnh lùng đối diện sự tuyệt vọng cùng cực, không ai có thể quay đầu lại được nữa.",
        "body_3": "Thời khắc quyết định đã điểm, số phận của cả hai người sẽ rơi vào vực thẳm hay tìm thấy lối thoát?",
        "call_to_action": "Bấm follow ngay để không bỏ lỡ diễn biến nghẹt thở ở chap tiếp theo!",
    },
    "humorous": {
        "hook": "Tưởng được lấy vợ hiền thục, ai dè rước ngay 'nóc nhà' chiến thần!",
        "body_1": "Thầy tu vừa đọc kinh xong thì cô dâu đã kịp lườm chú rể cháy cả mắt rồi.",
        "body_2": "Cưới xin gì tầm này khi mà trong đầu hai anh chị chỉ toàn mưu ma chước quỷ để dìm nhau.",
        "body_3": "Đúng là hảo bằng hữu trong game nhưng ngoài đời thì ai là gà ai là thóc còn chưa biết đâu nhé.",
        "call_to_action": "Thả ngay một tim và follow kênh để hóng tiếp màn combat nảy lửa này nào!",
    },
    "romantic": {
        "hook": "Khoảnh khắc hai ánh mắt chạm nhau, mọi định kiến dường như tan biến.",
        "body_1": "Trước thánh đường thiêng liêng, lời thề nguyện như khắc sâu vào từng nhịp đập con tim.",
        "body_2": "Dù phía trước là giông bão, chỉ cần một cái nắm tay ấm áp cũng đủ để vượt qua tất cả.",
        "body_3": "Tình cảm chân thành ấy liệu có chạm đến được nơi sâu thẳm nhất trong tâm hồn đối phương?",
        "call_to_action": "Đăng ký kênh để cùng theo dõi câu chuyện tình ngọt ngào này nhé!",
    },
}


def estimate_text_duration(text: str) -> float:
    """Calculate realistic speech duration based on Vietnamese word count."""
    words = len(text.strip().split())
    # Minimum 1.5s, roughly 3.2 words per second
    raw_sec = max(1.5, words / WORDS_PER_SECOND)
    return round(raw_sec, 2)


def generate_fallback_script(
    ocr_texts: Sequence[str],
    story_style: str = "dramatic",
    target_duration_sec: int = 45,
    project_id: str = "default_project",
) -> GeneratedScriptResponse:
    """Generates high-fidelity structured script segments using deterministic templates & OCR context."""
    style_key = story_style if story_style in SUPPORTED_STYLES else "dramatic"
    templates = FALLBACK_TEMPLATES[style_key]

    # Incorporate OCR context if available
    context_hint = ""
    valid_texts = [t.strip() for t in ocr_texts if t and len(t.strip()) > 3]
    if valid_texts:
        context_hint = f" ({valid_texts[0][:40]}...)"

    segments: list[ScriptSegment] = []

    # 1. Hook (0-3s)
    hook_text = templates["hook"]
    segments.append(
        ScriptSegment(
            id=f"SEG_{uuid.uuid4().hex[:6]}_01",
            section_type="hook",
            text=hook_text,
            estimated_duration=estimate_text_duration(hook_text),
            suggested_effect="punch_zoom",
        )
    )

    # 2. Body segments (3-4 parts)
    body_keys = ["body_1", "body_2", "body_3"]
    effects = ["zoom_in", "pan_down", "zoom_in"]
    for idx, (b_key, effect) in enumerate(zip(body_keys, effects), start=2):
        b_text = templates[b_key]
        if idx == 2 and context_hint:
            b_text = f"{b_text[:-1]}{context_hint}."
        segments.append(
            ScriptSegment(
                id=f"SEG_{uuid.uuid4().hex[:6]}_{idx:02d}",
                section_type="body",
                text=b_text,
                estimated_duration=estimate_text_duration(b_text),
                suggested_effect=effect,
            )
        )

    # 3. Call to Action
    cta_text = templates["call_to_action"]
    segments.append(
        ScriptSegment(
            id=f"SEG_{uuid.uuid4().hex[:6]}_{len(segments)+1:02d}",
            section_type="call_to_action",
            text=cta_text,
            estimated_duration=estimate_text_duration(cta_text),
            suggested_effect="zoom_out",
        )
    )

    # Calculate total duration
    total_dur = round(sum(s.estimated_duration for s in segments), 2)

    return GeneratedScriptResponse(
        project_id=project_id,
        story_style=style_key,
        total_duration=total_dur,
        segments=segments,
    )


def generate_script(
    ocr_texts: Sequence[str],
    story_style: str = "dramatic",
    target_duration_sec: int = 45,
    project_id: str = "default_project",
) -> GeneratedScriptResponse:
    """End-to-end script generation with LLM integration and robust fallback.

    Args:
        ocr_texts: List of extracted dialogue or text strings from comic pages.
        story_style: "dramatic", "humorous", or "romantic".
        target_duration_sec: Target video duration (default 45s).
        project_id: Project identifier.

    Returns:
        GeneratedScriptResponse with validated segments.
    """
    style_key = story_style.lower().strip() if story_style else "dramatic"
    if style_key not in SUPPORTED_STYLES:
        style_key = "dramatic"

    # Try calling local LLM via ollama_text if available
    try:
        from app.services.ollama_text import call_text_model

        sys_prompt = STYLE_SYSTEM_PROMPTS[style_key]
        ocr_context = "\n".join(f"- {t.strip()}" for t in ocr_texts if t.strip())

        prompt = (
            f"{sys_prompt}\n\n"
            f"Dưới đây là nội dung trích xuất từ các trang truyện:\n"
            f"{ocr_context}\n\n"
            f"YÊU CẦU:\n"
            f"Hãy viết một kịch bản review video ngắn (khoảng {target_duration_sec} giây) bằng tiếng Việt.\n"
            f"Chia kịch bản thành các phân đoạn (segments) rõ ràng theo JSON schema sau:\n"
            f"```json\n"
            f"{{\n"
            f'  "segments": [\n'
            f'    {{"id": "SEG_01", "section_type": "hook", "text": "...", "estimated_duration": 3.0, "suggested_effect": "punch_zoom"}},\n'
            f'    {{"id": "SEG_02", "section_type": "body", "text": "...", "estimated_duration": 8.5, "suggested_effect": "zoom_in"}},\n'
            f'    {{"id": "SEG_03", "section_type": "call_to_action", "text": "...", "estimated_duration": 3.5, "suggested_effect": "zoom_out"}}\n'
            f'  ]\n'
            f"}}\n"
            f"```\n"
            f"Chỉ trả về định dạng JSON hợp lệ, không giải thích gì thêm."
        )

        resp_dict = call_text_model(prompt=prompt, timeout=15, json_mode=True)
        raw_segments = resp_dict.get("segments", [])

        if raw_segments and isinstance(raw_segments, list):
            parsed_segments: list[ScriptSegment] = []
            for i, seg in enumerate(raw_segments):
                sid = seg.get("id", f"SEG_{i+1:02d}")
                sec_type = seg.get("section_type", "body")
                if sec_type not in SECTION_TYPES:
                    sec_type = "body"
                txt = seg.get("text", "").strip()
                if not txt:
                    continue
                dur = float(seg.get("estimated_duration", estimate_text_duration(txt)))
                effect = seg.get("suggested_effect", "zoom_in")
                if effect not in SUGGESTED_EFFECTS:
                    effect = "zoom_in"

                parsed_segments.append(
                    ScriptSegment(
                        id=sid,
                        section_type=sec_type,
                        text=txt,
                        estimated_duration=round(dur, 2),
                        suggested_effect=effect,
                    )
                )

            if len(parsed_segments) >= 2:
                total_dur = round(sum(s.estimated_duration for s in parsed_segments), 2)
                return GeneratedScriptResponse(
                    project_id=project_id,
                    story_style=style_key,
                    total_duration=total_dur,
                    segments=parsed_segments,
                )
    except Exception as exc:
        logger.info(f"LLM script generation bypassed/failed ({exc}), using deterministic fallback.")

    # Graceful fallback
    return generate_fallback_script(
        ocr_texts=ocr_texts,
        story_style=style_key,
        target_duration_sec=target_duration_sec,
        project_id=project_id,
    )

