from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class HypothesisLevel(str, Enum):
    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    VENUE = "venue"


class HypothesisStatus(str, Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    ELIMINATED = "eliminated"


class Hypothesis(BaseModel):
    id: str = Field(description="Unique identifier for this hypothesis")
    description: str = Field(description="What the hypothesis proposes")
    level: HypothesisLevel = Field(description="Geographic specificity level")
    status: HypothesisStatus = Field(default=HypothesisStatus.ACTIVE)
    region: str | None = Field(default=None, description="Proposed region/country")
    place_type: str | None = Field(default=None, description="Proposed venue category")
    reasoning: str = Field(description="Why this hypothesis was generated")
    supporting_clue_ids: list[str] = Field(
        default_factory=list, description="Clue IDs that support this hypothesis"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Current confidence in this hypothesis"
    )
    parent_hypothesis_id: str | None = Field(
        default=None,
        description="If this is a sub-hypothesis, the parent hypothesis ID",
    )
    elimination_reason: str | None = Field(
        default=None, description="Why this hypothesis was eliminated"
    )
