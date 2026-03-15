from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ClueSource(str, Enum):
    IMAGE_ANALYSIS = "image_analysis"
    EXIF = "exif"
    OCR = "ocr"
    REVERSE_IMAGE_SEARCH = "reverse_image_search"
    WEB_SEARCH = "web_search"
    MAPS = "maps"
    USER_PROVIDED = "user_provided"


class ClueCategory(str, Enum):
    TEXT = "text"
    SIGNAGE = "signage"
    BRAND = "brand"
    ARCHITECTURE = "architecture"
    VEGETATION = "vegetation"
    TERRAIN = "terrain"
    ROAD_INFRASTRUCTURE = "road_infrastructure"
    WEATHER_LIGHTING = "weather_lighting"
    INTERIOR = "interior"
    VEHICLE = "vehicle"
    LANGUAGE = "language"
    METADATA = "metadata"
    OTHER = "other"


class Clue(BaseModel):
    id: str = Field(description="Unique identifier for this clue")
    description: str = Field(description="What was observed")
    category: ClueCategory = Field(description="Type of clue")
    source: ClueSource = Field(description="How the clue was obtained")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the observation itself")
    raw_value: str | None = Field(
        default=None, description="Raw extracted value (e.g. OCR text, EXIF field)"
    )
    region_hint: str | None = Field(
        default=None,
        description="If this clue suggests a region, note it here",
    )
