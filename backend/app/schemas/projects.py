from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    content_type: Literal["short", "long"]


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
