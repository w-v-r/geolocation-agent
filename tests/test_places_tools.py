"""Tests for places / POI tools (mocked Google Maps Places API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


class TestSearchPlacesNearby:
    @patch("geolocation_agent.tools.places_tools.get_settings")
    def test_returns_nearby_places(self, mock_settings):
        mock_settings.return_value.google_maps_api_key = "test-key"

        mock_results = {
            "results": [
                {
                    "name": "Coolangatta Estate",
                    "place_id": "place_1",
                    "vicinity": "1335 Bolong Rd, Shoalhaven Heads",
                    "geometry": {"location": {"lat": -34.85, "lng": 150.73}},
                    "types": ["food", "point_of_interest"],
                    "rating": 4.3,
                    "user_ratings_total": 500,
                },
            ]
        }

        with patch("googlemaps.Client") as MockClient:
            mock_gmaps = MagicMock()
            mock_gmaps.places_nearby.return_value = mock_results
            MockClient.return_value = mock_gmaps

            from geolocation_agent.tools.places_tools import search_places_nearby

            result = search_places_nearby.invoke({
                "lat": -34.85,
                "lng": 150.73,
                "radius": 5000,
                "keyword": "winery",
            })
            data = json.loads(result)
            assert len(data) == 1
            assert data[0]["name"] == "Coolangatta Estate"
            assert data[0]["rating"] == 4.3


class TestSearchPlacesText:
    @patch("geolocation_agent.tools.places_tools.get_settings")
    def test_returns_text_search_results(self, mock_settings):
        mock_settings.return_value.google_maps_api_key = "test-key"

        mock_results = {
            "results": [
                {
                    "name": "Crooked River Winery",
                    "place_id": "place_2",
                    "formatted_address": "123 Wine Rd, Berry NSW",
                    "geometry": {"location": {"lat": -34.78, "lng": 150.70}},
                    "types": ["food"],
                    "rating": 4.5,
                    "user_ratings_total": 200,
                },
            ]
        }

        with patch("googlemaps.Client") as MockClient:
            mock_gmaps = MagicMock()
            mock_gmaps.places.return_value = mock_results
            MockClient.return_value = mock_gmaps

            from geolocation_agent.tools.places_tools import search_places_text

            result = search_places_text.invoke({"query": "wineries near Berry NSW"})
            data = json.loads(result)
            assert len(data) == 1
            assert data[0]["name"] == "Crooked River Winery"


class TestGetPlaceDetails:
    @patch("geolocation_agent.tools.places_tools.get_settings")
    def test_returns_full_details(self, mock_settings):
        mock_settings.return_value.google_maps_api_key = "test-key"

        mock_result = {
            "result": {
                "name": "Coolangatta Estate",
                "place_id": "place_1",
                "formatted_address": "1335 Bolong Rd, Shoalhaven Heads NSW",
                "geometry": {"location": {"lat": -34.85, "lng": 150.73}},
                "formatted_phone_number": "(02) 1234 5678",
                "website": "https://coolangattaestate.com",
                "types": ["food", "point_of_interest"],
                "rating": 4.3,
                "user_ratings_total": 500,
                "opening_hours": {"weekday_text": ["Mon: 10am-5pm"]},
                "reviews": [
                    {"text": "Beautiful vineyard", "rating": 5},
                ],
                "photos": [
                    {"photo_reference": "ref123", "width": 800, "height": 600},
                ],
            }
        }

        with patch("googlemaps.Client") as MockClient:
            mock_gmaps = MagicMock()
            mock_gmaps.place.return_value = mock_result
            MockClient.return_value = mock_gmaps

            from geolocation_agent.tools.places_tools import get_place_details

            result = get_place_details.invoke({"place_id": "place_1"})
            data = json.loads(result)
            assert data["name"] == "Coolangatta Estate"
            assert data["website"] == "https://coolangattaestate.com"
            assert len(data["photos"]) == 1
            assert len(data["reviews"]) == 1
