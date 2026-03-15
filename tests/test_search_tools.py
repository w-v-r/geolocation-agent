"""Tests for search tools (mocked external APIs)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


class TestWebSearch:
    @patch("geolocation_agent.tools.search_tools.get_settings")
    @patch("geolocation_agent.tools.search_tools.TavilyClient")
    def test_returns_structured_results(self, MockTavily, mock_settings):
        mock_settings.return_value.tavily_api_key = "test-key"

        mock_response = {
            "results": [
                {
                    "title": "Berry Winery NSW",
                    "url": "https://example.com/berry-winery",
                    "content": "A beautiful winery on the NSW South Coast",
                    "score": 0.95,
                },
                {
                    "title": "Shoalhaven Wine Region",
                    "url": "https://example.com/shoalhaven",
                    "content": "Wineries and vineyards near Berry",
                    "score": 0.87,
                },
            ]
        }

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        MockTavily.return_value = mock_client

        from geolocation_agent.tools.search_tools import web_search

        result = web_search.invoke({"query": "wineries near Berry NSW"})
        data = json.loads(result)
        assert len(data) == 2
        assert data[0]["title"] == "Berry Winery NSW"
        assert data[0]["url"] == "https://example.com/berry-winery"
        assert data[0]["score"] == 0.95

    @patch("geolocation_agent.tools.search_tools.get_settings")
    @patch("geolocation_agent.tools.search_tools.TavilyClient")
    def test_handles_empty_results(self, MockTavily, mock_settings):
        mock_settings.return_value.tavily_api_key = "test-key"

        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        MockTavily.return_value = mock_client

        from geolocation_agent.tools.search_tools import web_search

        result = web_search.invoke({"query": "nonexistent place xyz123"})
        data = json.loads(result)
        assert len(data) == 0


class TestRunGoogleLens:
    @patch("geolocation_agent.tools.search_tools.get_settings")
    @patch("geolocation_agent.tools.search_tools.GoogleSearch")
    def test_returns_visual_matches(self, MockGoogleSearch, mock_settings):
        mock_settings.return_value.serpapi_api_key = "test-key"

        mock_result = {
            "visual_matches": [
                {
                    "title": "Sydney Opera House",
                    "link": "https://example.com/opera-house",
                    "source": "wikipedia.org",
                    "thumbnail": "https://example.com/thumb.jpg",
                },
            ],
            "knowledge_graph": [
                {"title": "Sydney Opera House", "subtitle": "Performing arts venue"},
            ],
        }

        mock_search = MagicMock()
        mock_search.get_dict.return_value = mock_result
        MockGoogleSearch.return_value = mock_search

        from geolocation_agent.tools.search_tools import _run_google_lens

        result = _run_google_lens("https://example.com/image.jpg")
        data = json.loads(result)
        assert len(data["visual_matches"]) == 1
        assert data["visual_matches"][0]["title"] == "Sydney Opera House"
        assert len(data["knowledge_graph"]) == 1

    @patch("geolocation_agent.tools.search_tools.get_settings")
    @patch("geolocation_agent.tools.search_tools.GoogleSearch")
    def test_handles_no_matches(self, MockGoogleSearch, mock_settings):
        mock_settings.return_value.serpapi_api_key = "test-key"

        mock_search = MagicMock()
        mock_search.get_dict.return_value = {}
        MockGoogleSearch.return_value = mock_search

        from geolocation_agent.tools.search_tools import _run_google_lens

        result = _run_google_lens("https://example.com/image.jpg")
        data = json.loads(result)
        assert data["visual_matches"] == []
        assert data["knowledge_graph"] == []
