"""Structured memory / evidence tracker for the geolocation investigation."""

from __future__ import annotations

import json
import uuid

from langchain_core.tools import tool


def _make_id() -> str:
    return uuid.uuid4().hex[:8]


@tool
def add_clue(
    description: str,
    category: str,
    source: str,
    confidence: float,
    raw_value: str = "",
    region_hint: str = "",
) -> str:
    """Record a clue extracted from the image or investigation.

    Args:
        description: What was observed
            (e.g. "Red roof tiles typical of Mediterranean").
        category: Clue category (text, signage, brand, architecture,
            vegetation, terrain, road_infrastructure, weather_lighting,
            interior, vehicle, language, metadata, other).
        source: How the clue was obtained (image_analysis, exif, ocr, reverse_image_search,
                web_search, maps, user_provided).
        confidence: Confidence in the observation (0.0 to 1.0).
        raw_value: Raw extracted value if applicable (e.g. OCR text).
        region_hint: If the clue suggests a region, note it here.

    Returns:
        JSON string with the recorded clue including its assigned ID.
    """
    clue = {
        "id": f"clue_{_make_id()}",
        "description": description,
        "category": category,
        "source": source,
        "confidence": max(0.0, min(1.0, confidence)),
        "raw_value": raw_value,
        "region_hint": region_hint,
    }
    return json.dumps(clue, indent=2)


@tool
def add_hypothesis(
    description: str,
    level: str,
    reasoning: str,
    confidence: float,
    region: str = "",
    place_type: str = "",
    supporting_clue_ids: str = "",
    parent_hypothesis_id: str = "",
) -> str:
    """Record a hypothesis about the photo's location.

    Args:
        description: What the hypothesis proposes (e.g. "Photo taken at a coastal winery in NSW").
        level: Geographic specificity (country, region, city, venue).
        reasoning: Why this hypothesis was generated.
        confidence: Current confidence in this hypothesis (0.0 to 1.0).
        region: Proposed region/country.
        place_type: Proposed venue category.
        supporting_clue_ids: Comma-separated list of clue IDs that support this.
        parent_hypothesis_id: If this is a sub-hypothesis, the parent ID.

    Returns:
        JSON string with the recorded hypothesis including its assigned ID.
    """
    clue_ids = [c.strip() for c in supporting_clue_ids.split(",") if c.strip()]

    hypothesis = {
        "id": f"hyp_{_make_id()}",
        "description": description,
        "level": level,
        "status": "active",
        "region": region,
        "place_type": place_type,
        "reasoning": reasoning,
        "supporting_clue_ids": clue_ids,
        "confidence": max(0.0, min(1.0, confidence)),
        "parent_hypothesis_id": parent_hypothesis_id or None,
        "elimination_reason": None,
    }
    return json.dumps(hypothesis, indent=2)


@tool
def add_candidate(
    name: str,
    hypothesis_id: str,
    confidence: float,
    latitude: float | None = None,
    longitude: float | None = None,
    address: str = "",
    place_type: str = "",
) -> str:
    """Record a candidate location that might match the photo.

    Args:
        name: Name of the candidate location.
        hypothesis_id: Which hypothesis this candidate was generated from.
        confidence: Current confidence in this candidate (0.0 to 1.0).
        latitude: Latitude of the candidate.
        longitude: Longitude of the candidate.
        address: Address of the candidate.
        place_type: Type of place.

    Returns:
        JSON string with the recorded candidate including its assigned ID.
    """
    candidate = {
        "id": f"cand_{_make_id()}",
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "place_type": place_type,
        "hypothesis_id": hypothesis_id,
        "confidence": max(0.0, min(1.0, confidence)),
        "evidence_for": [],
        "evidence_against": [],
        "eliminated": False,
        "elimination_reason": None,
    }
    return json.dumps(candidate, indent=2)


@tool
def add_evidence(
    hypothesis_id: str,
    evidence_type: str,
    description: str,
    source: str,
    weight: float = 0.5,
    candidate_id: str = "",
) -> str:
    """Record a piece of evidence for or against a hypothesis or candidate.

    Args:
        hypothesis_id: Which hypothesis this evidence relates to.
        evidence_type: Whether this supports, contradicts, or is neutral
                       (supporting, contradicting, neutral).
        description: What the evidence is.
        source: Where it came from (tool name, URL, etc.).
        weight: How significant this evidence is (0.0 to 1.0).
        candidate_id: Which specific candidate this relates to, if any.

    Returns:
        JSON string with the recorded evidence entry including its assigned ID.
    """
    entry = {
        "id": f"ev_{_make_id()}",
        "hypothesis_id": hypothesis_id,
        "candidate_id": candidate_id or None,
        "evidence_type": evidence_type,
        "description": description,
        "source": source,
        "weight": max(0.0, min(1.0, weight)),
    }
    return json.dumps(entry, indent=2)


@tool
def eliminate_candidate(candidate_id: str, reason: str) -> str:
    """Mark a candidate as eliminated with a reason.

    The candidate is kept in the evidence log but flagged as eliminated.

    Args:
        candidate_id: The ID of the candidate to eliminate.
        reason: Why this candidate was eliminated.

    Returns:
        JSON string confirming the elimination.
    """
    return json.dumps({
        "action": "eliminate_candidate",
        "candidate_id": candidate_id,
        "eliminated": True,
        "elimination_reason": reason,
    }, indent=2)


@tool
def update_confidence(candidate_id: str, new_confidence: float, reason: str) -> str:
    """Update the confidence score for a candidate.

    Args:
        candidate_id: The ID of the candidate to update.
        new_confidence: New confidence score (0.0 to 1.0).
        reason: Why the confidence changed.

    Returns:
        JSON string confirming the update.
    """
    return json.dumps({
        "action": "update_confidence",
        "candidate_id": candidate_id,
        "new_confidence": max(0.0, min(1.0, new_confidence)),
        "reason": reason,
    }, indent=2)


@tool
def get_investigation_summary(
    clues: str = "[]",
    hypotheses: str = "[]",
    candidates: str = "[]",
    evidence_log: str = "[]",
    eliminated: str = "[]",
) -> str:
    """Generate a formatted summary of the current investigation state.

    Pass the current state data as JSON strings to get a readable summary.

    Args:
        clues: JSON string of current clues list.
        hypotheses: JSON string of current hypotheses list.
        candidates: JSON string of current candidates list.
        evidence_log: JSON string of current evidence log.
        eliminated: JSON string of eliminated candidates.

    Returns:
        Formatted markdown summary of the investigation state.
    """
    try:
        clues_list = json.loads(clues) if clues else []
        hyp_list = json.loads(hypotheses) if hypotheses else []
        cand_list = json.loads(candidates) if candidates else []
        ev_list = json.loads(evidence_log) if evidence_log else []
        elim_list = json.loads(eliminated) if eliminated else []
    except json.JSONDecodeError:
        return "Error: Could not parse investigation state data."

    lines = ["# Investigation Summary\n"]

    lines.append(f"## Clues ({len(clues_list)})")
    for c in clues_list:
        lines.append(f"- [{c.get('category', '?')}] {c.get('description', '?')} "
                      f"(confidence: {c.get('confidence', '?')})")

    lines.append(f"\n## Hypotheses ({len(hyp_list)})")
    active = [h for h in hyp_list if h.get("status") == "active"]
    for h in sorted(active, key=lambda x: x.get("confidence", 0), reverse=True):
        lines.append(f"- [{h.get('level', '?')}] {h.get('description', '?')} "
                      f"(confidence: {h.get('confidence', '?')})")

    active_count = len([c for c in cand_list if not c.get("eliminated")])
    lines.append(f"\n## Active Candidates ({active_count})")
    active_cands = [c for c in cand_list if not c.get("eliminated")]
    for c in sorted(active_cands, key=lambda x: x.get("confidence", 0), reverse=True):
        lines.append(f"- {c.get('name', '?')} (confidence: {c.get('confidence', '?')})")

    lines.append(f"\n## Evidence ({len(ev_list)})")
    for e in ev_list[-10:]:
        ev_type = e.get("evidence_type", "")
        prefix = "+" if ev_type == "supporting" else "-" if ev_type == "contradicting" else "~"
        lines.append(f"  {prefix} {e.get('description', '?')} [source: {e.get('source', '?')}]")

    if elim_list:
        lines.append(f"\n## Eliminated ({len(elim_list)})")
        for e in elim_list:
            lines.append(f"- {e.get('name', '?')}: {e.get('elimination_reason', '?')}")

    return "\n".join(lines)
