"""Tests for evidence tracker tools (pure logic, no mocks needed)."""

from __future__ import annotations

import json

from geolocation_agent.tools.evidence_tracker import (
    add_candidate,
    add_clue,
    add_evidence,
    add_hypothesis,
    eliminate_candidate,
    get_investigation_summary,
    update_confidence,
)


class TestAddClue:
    def test_creates_clue_with_id(self):
        result = add_clue.invoke({
            "description": "Red roof tiles typical of Mediterranean architecture",
            "category": "architecture",
            "source": "image_analysis",
            "confidence": 0.8,
        })
        data = json.loads(result)
        assert data["id"].startswith("clue_")
        assert data["description"] == "Red roof tiles typical of Mediterranean architecture"
        assert data["category"] == "architecture"
        assert data["confidence"] == 0.8

    def test_clamps_confidence(self):
        result = add_clue.invoke({
            "description": "test",
            "category": "other",
            "source": "image_analysis",
            "confidence": 1.5,
        })
        data = json.loads(result)
        assert data["confidence"] == 1.0

    def test_includes_optional_fields(self):
        result = add_clue.invoke({
            "description": "Sign reads 'Rue de la Paix'",
            "category": "text",
            "source": "ocr",
            "confidence": 0.9,
            "raw_value": "Rue de la Paix",
            "region_hint": "France",
        })
        data = json.loads(result)
        assert data["raw_value"] == "Rue de la Paix"
        assert data["region_hint"] == "France"


class TestAddHypothesis:
    def test_creates_hypothesis_with_id(self):
        result = add_hypothesis.invoke({
            "description": "Photo taken in southern France",
            "level": "region",
            "reasoning": "Mediterranean architecture and French text visible",
            "confidence": 0.6,
            "region": "southern France",
        })
        data = json.loads(result)
        assert data["id"].startswith("hyp_")
        assert data["status"] == "active"
        assert data["region"] == "southern France"

    def test_parses_supporting_clue_ids(self):
        result = add_hypothesis.invoke({
            "description": "test hypothesis",
            "level": "country",
            "reasoning": "test",
            "confidence": 0.5,
            "supporting_clue_ids": "clue_abc123, clue_def456",
        })
        data = json.loads(result)
        assert data["supporting_clue_ids"] == ["clue_abc123", "clue_def456"]


class TestAddCandidate:
    def test_creates_candidate(self):
        result = add_candidate.invoke({
            "name": "Chateau de Versailles",
            "hypothesis_id": "hyp_abc123",
            "confidence": 0.7,
            "latitude": 48.8049,
            "longitude": 2.1204,
            "address": "Place d'Armes, 78000 Versailles",
        })
        data = json.loads(result)
        assert data["id"].startswith("cand_")
        assert data["name"] == "Chateau de Versailles"
        assert data["eliminated"] is False


class TestAddEvidence:
    def test_creates_supporting_evidence(self):
        result = add_evidence.invoke({
            "hypothesis_id": "hyp_abc123",
            "evidence_type": "supporting",
            "description": "Google Lens matched building facade to Versailles",
            "source": "reverse_image_search",
            "weight": 0.9,
        })
        data = json.loads(result)
        assert data["id"].startswith("ev_")
        assert data["evidence_type"] == "supporting"
        assert data["weight"] == 0.9

    def test_creates_contradicting_evidence(self):
        result = add_evidence.invoke({
            "hypothesis_id": "hyp_abc123",
            "evidence_type": "contradicting",
            "description": "Vegetation does not match French climate",
            "source": "image_analysis",
        })
        data = json.loads(result)
        assert data["evidence_type"] == "contradicting"


class TestEliminateCandidate:
    def test_returns_elimination_record(self):
        result = eliminate_candidate.invoke({
            "candidate_id": "cand_abc123",
            "reason": "Street View shows completely different building",
        })
        data = json.loads(result)
        assert data["candidate_id"] == "cand_abc123"
        assert data["eliminated"] is True
        assert "Street View" in data["elimination_reason"]


class TestUpdateConfidence:
    def test_returns_update_record(self):
        result = update_confidence.invoke({
            "candidate_id": "cand_abc123",
            "new_confidence": 0.85,
            "reason": "Satellite imagery confirms vineyard layout matches",
        })
        data = json.loads(result)
        assert data["new_confidence"] == 0.85


class TestGetInvestigationSummary:
    def test_formats_empty_state(self):
        result = get_investigation_summary.invoke({})
        assert "Investigation Summary" in result

    def test_formats_populated_state(self):
        clues = json.dumps([
            {"id": "c1", "category": "text", "description": "French sign", "confidence": 0.9},
        ])
        hypotheses = json.dumps([
            {"id": "h1", "level": "country", "description": "France",
             "status": "active", "confidence": 0.7},
        ])
        candidates = json.dumps([
            {"id": "ca1", "name": "Paris", "confidence": 0.6, "eliminated": False},
        ])
        evidence = json.dumps([
            {"id": "e1", "evidence_type": "supporting",
             "description": "French text visible", "source": "ocr"},
        ])

        result = get_investigation_summary.invoke({
            "clues": clues,
            "hypotheses": hypotheses,
            "candidates": candidates,
            "evidence_log": evidence,
        })
        assert "French sign" in result
        assert "France" in result
        assert "Paris" in result
        assert "French text visible" in result
