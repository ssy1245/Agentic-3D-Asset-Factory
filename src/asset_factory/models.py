from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Stage(StrEnum):
    design = "design"
    turnaround = "turnaround"
    head = "head"
    body = "body"
    hair = "hair"


class Region(BaseModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def bounds(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("选区超出图片边界")
        return self


class BrushPoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class BrushStroke(BaseModel):
    points: list[BrushPoint] = Field(min_length=1, max_length=2000)
    width: float = Field(default=0.006, ge=0.001, le=0.03)


class GenerateRequest(BaseModel):
    stage: Stage
    feedback: str = Field(default="", max_length=4000)
    source_revision: str | None = None
    design_mode: Literal["text", "image"] | None = None
    input_image_id: str | None = None
    feedback_image_ids: list[str] = Field(default_factory=list, max_length=3)
    brush_strokes: list[BrushStroke] = Field(default_factory=list, max_length=100)
    region: Region | None = None
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9-]+$")

    @model_validator(mode="after")
    def annotation_limit(self):
        if sum(len(stroke.points) for stroke in self.brush_strokes) > 10000:
            raise ValueError("圈画内容过多，请简化标注")
        return self
