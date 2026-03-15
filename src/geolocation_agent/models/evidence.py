from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"


class EvidenceEntry(BaseModel):
    id: str = Field(description="Unique identifier for this evidence entry")
    hypothesis_id: str = Field(description="Which hypothesis this evidence relates to")
    candidate_id: str | None = Field(
        default=None, description="Which candidate this evidence relates to"
    )
    evidence_type: EvidenceType = Field(description="Whether this supports or contradicts")
    description: str = Field(description="What the evidence is")
    source: str = Field(description="Where the evidence came from (tool name, URL, etc.)")
    weight: float = Field(
        ge=0.0, le=1.0, default=0.5, description="How significant this evidence is"
    )


class Candidate(BaseModel):
    id: str = Field(description="Unique identifier for this candidate")
    name: str = Field(description="Name of the candidate location")
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    address: str | None = Field(default=None)
    place_type: str | None = Field(default=None)
    hypothesis_id: str = Field(description="Which hypothesis this candidate was generated from")
    confidence: float = Field(ge=0.0, le=1.0, description="Current confidence in this candidate")
    evidence_for: list[str] = Field(
        default_factory=list, description="Evidence entry IDs supporting this candidate"
    )
    evidence_against: list[str] = Field(
        default_factory=list, description="Evidence entry IDs contradicting this candidate"
    )
    eliminated: bool = Field(default=False)
    elimination_reason: str | None = Field(default=None)


class ConfidenceLevel(str, Enum):
    SPECULATIVE = "speculative"
    PLAUSIBLE = "plausible"
    CONFIDENT = "confident"
    CERTAIN = "certain"


class FinalAnswer(BaseModel):
    best_candidate: Candidate = Field(description="The most likely location")
    alternative_candidates: list[Candidate] = Field(
        default_factory=list, description="Other plausible locations"
    )
    region_confidence: ConfidenceLevel = Field(description="Confidence in the identified region")
    place_type_confidence: ConfidenceLevel = Field(
        description="Confidence in the identified place type"
    )
    venue_confidence: ConfidenceLevel = Field(
        description="Confidence in the specific venue"
    )
    key_evidence: list[str] = Field(description="Most important evidence that led to the answer")
    unresolved_uncertainties: list[str] = Field(
        default_factory=list, description="What remains unknown"
    )
    reasoning_summary: str = Field(description="Narrative summary of the investigation")
