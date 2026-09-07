from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    id: str | None = None
    name: str
    content_type: Literal["short", "long"]
    story_style: Literal["dramatic", "humorous", "romantic"] | None = "dramatic"


class ShortScriptCreate(BaseModel):
    style: Literal["natural", "funny", "emotional", "dramatic"]


class ShortScriptSegmentEdit(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class StoryEventEdit(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source_revision: str = Field(min_length=1, max_length=128)


class StoryEvidenceResolution(BaseModel):
    source_revision: str = Field(min_length=1, max_length=128)


class StoryEvidenceAdd(StoryEvidenceResolution):
    text: str = Field(min_length=1, max_length=2000)


class GenerateScriptRequest(BaseModel):
    story_style: str = Field(default="dramatic", description="Story style or alias (dramatic, humorous, romantic, romcom, etc.)")
    target_duration: float = Field(default=45.0, ge=1.0, le=600.0, description="Target duration in seconds")
    panel_id: str | None = Field(default=None, description="Optional target panel ID")
    page_order: int | None = Field(default=None, description="Optional page sequence number")
    image_path: str | None = Field(default=None, description="Optional source image path")


class IngestChapterRequest(BaseModel):
    chapter_dir: str | None = None
    image_paths: list[str] | None = None


class AutoAlignChapterRequest(BaseModel):
    story_style: str = Field(default="dramatic", description="Story style or alias")
    target_duration: float = Field(default=45.0, ge=1.0, le=600.0, description="Target duration in seconds")
    target_panel_count: int = Field(default=8, ge=1, le=50, description="Target number of panels")
    custom_script: dict[str, Any] | None = None
    existing_script: dict[str, Any] | None = None


class ProjectRenderRequest(BaseModel):
    timeline: dict[str, Any] | None = None
    output_filename: str | None = None
    bgm_path: str | None = None
    story_style: str = Field(default="dramatic", description="Story style or alias")


