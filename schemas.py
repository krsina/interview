import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["dark_mode"])
    description: str | None = Field(None, examples=["Enable dark mode UI"])
    is_enabled: bool = Field(False)


class FeatureFlagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_enabled: bool | None = None


class FeatureFlagToggle(BaseModel):
    is_enabled: bool


class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class FeatureFlagListResponse(BaseModel):
    items: list[FeatureFlagResponse]
    total: int


class MessageResponse(BaseModel):
    detail: str


# --- User overrides ---


class FlagUserOverrideSet(BaseModel):
    is_enabled: bool


class FlagUserOverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    flag_id: uuid.UUID
    user_id: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class FlagUserOverrideListResponse(BaseModel):
    items: list[FlagUserOverrideResponse]
    total: int


# --- Evaluate ---


class EvaluateResponse(BaseModel):
    enabled: bool
    flag_id: uuid.UUID
    flag_name: str
    user_id: str
    source: str = Field(..., description="override | default")
