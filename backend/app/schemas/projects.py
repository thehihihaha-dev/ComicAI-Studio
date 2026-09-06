from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
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
    story_style: Literal["humorous", "dramatic", "romantic"] = "dramatic"
    target_duration: int = Field(default=45, ge=10, le=300)


class IngestChapterRequest(BaseModel):
    chapter_dir: str | None = None
    image_paths: list[str] | None = None


class AutoAlignChapterRequest(BaseModel):
    story_style: Literal["dramatic", "humorous", "romantic"] = "dramatic"
    target_duration: int = Field(default=45, ge=10, le=300)
    target_panel_count: int = Field(default=8, ge=6, le=10)
    custom_script: dict[str, Any] | None = None


class ProjectRenderRequest(BaseModel):
    timeline: dict[str, Any] | None = None
    output_filename: str | None = None
    bgm_path: str | None = None
    story_style: Literal["dramatic", "humorous", "romantic"] = "dramatic"


