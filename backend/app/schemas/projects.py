from typing import Literal

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    content_type: Literal["short", "long"]


class ShortScriptCreate(BaseModel):
    style: Literal["funny", "emotional", "dramatic"]
