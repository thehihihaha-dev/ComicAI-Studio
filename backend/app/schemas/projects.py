from typing import Literal

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
