"""Integration tests for the full geolocation agent pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from geolocation_agent.agent import build_graph, create_agent
from geolocation_agent.nodes import (
    extract_metadata,
    should_continue,
)


class TestExtractMetadata:
    def test_extracts_from_image_without_exif(self, test_image_path):
        state = {
            "image_path": test_image_path,
            "side_info": "",
            "clues": [],
        }
        result = extract_metadata(state)
        assert result["phase"] == "analyze"
        assert isinstance(result["clues"], list)
        assert len(result["messages"]) > 0


class TestShouldContinue:
    @patch("geolocation_agent.nodes.get_settings")
    def test_returns_report_when_confident(self, mock_settings):
        mock_settings.return_value.confidence_threshold = 0.8
        mock_settings.return_value.max_iterations = 10

        state = {"confidence": 0.85, "iteration": 2, "max_iterations": 10}
        assert should_continue(state) == "report"

    @patch("geolocation_agent.nodes.get_settings")
    def test_returns_report_when_max_iterations(self, mock_settings):
        mock_settings.return_value.confidence_threshold = 0.8
        mock_settings.return_value.max_iterations = 10

        state = {"confidence": 0.3, "iteration": 10, "max_iterations": 10}
        assert should_continue(state) == "report"

    @patch("geolocation_agent.nodes.get_settings")
    def test_returns_hypothesize_when_not_confident(self, mock_settings):
        mock_settings.return_value.confidence_threshold = 0.8
        mock_settings.return_value.max_iterations = 10

        state = {"confidence": 0.4, "iteration": 2, "max_iterations": 10}
        assert should_continue(state) == "hypothesize"


class TestBuildGraph:
    def test_graph_builds_without_error(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_compiles(self):
        agent = create_agent()
        assert agent is not None


class TestProduceReport:
    @patch("geolocation_agent.nodes.get_llm")
    def test_generates_final_answer(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_response = AIMessage(
            content="Based on the investigation, the photo was taken in Sydney."
        )
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        from geolocation_agent.nodes import produce_report

        state = {
            "image_path": "test.jpg",
            "candidates": [
                {
                    "id": "cand_1",
                    "name": "Sydney Opera House",
                    "latitude": -33.8568,
                    "longitude": 151.2153,
                    "confidence": 0.85,
                    "eliminated": False,
                },
            ],
            "evidence_log": [
                {
                    "id": "ev_1",
                    "evidence_type": "supporting",
                    "description": "Building shape matches Opera House",
                    "source": "reverse_image_search",
                },
            ],
            "eliminated": [],
            "confidence": 0.85,
            "iteration": 3,
            "max_iterations": 10,
            "side_info": "",
            "clues": [],
            "hypotheses": [],
        }

        result = produce_report(state)
        assert result["final_answer"] is not None
        assert result["final_answer"]["best_candidate"]["name"] == "Sydney Opera House"
        assert result["final_answer"]["region_confidence"] == "confident"
        assert result["phase"] == "complete"


class TestFullPipelineMocked:
    """Test the full pipeline with all LLM calls mocked."""

    @patch("geolocation_agent.nodes.get_llm")
    def test_pipeline_reaches_report(self, mock_get_llm, test_image_path):
        mock_llm = MagicMock()

        analyze_response = AIMessage(content="I can see a red building and a sign.")
        analyze_response.tool_calls = []

        hypothesize_response = AIMessage(content="I hypothesize this is in Australia.")
        hypothesize_response.tool_calls = []

        investigate_response = AIMessage(content="Investigation complete.")
        investigate_response.tool_calls = []

        report_response = AIMessage(content="The photo was taken in Sydney, Australia.")
        report_response.tool_calls = []

        mock_llm.invoke.side_effect = [
            analyze_response,
            hypothesize_response,
            investigate_response,
            report_response,
        ]
        mock_llm.bind_tools.return_value = mock_llm

        mock_get_llm.return_value = mock_llm

        agent = create_agent()

        initial_state = {
            "image_path": test_image_path,
            "side_info": "",
            "messages": [],
            "clues": [],
            "hypotheses": [],
            "candidates": [],
            "evidence_log": [],
            "eliminated": [],
            "iteration": 0,
            "max_iterations": 1,
            "phase": "extract_metadata",
            "confidence": 0.0,
            "final_answer": None,
        }

        result = agent.invoke(initial_state)

        assert result["phase"] == "complete"
        assert result["final_answer"] is not None
        assert result["iteration"] >= 1
