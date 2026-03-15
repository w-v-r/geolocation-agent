"""Tests for maps and geospatial tools (mocked Google Maps API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


class TestGeocode:
    @patch("geolocation_agent.tools.maps_tools.get_settings")
    def test_returns_coordinates(self, mock_settings):
        mock_settings.return_value.google_maps_api_key = "test-key"

        mock_results = [{
            "geometry": {"location": {"lat": -33.8688, "lng": 151.2093}},
            "formatted_address": "Sydney NSW, Australia",
            "place_id": "ChIJP3Sa8ziYEmsRUKgyFmh9AQM",
            "types": ["locality"],
        }]

        with patch("googlemaps.Client") as MockClient:
            mock_gmaps = MagicMock()
            mock_gmaps.geocode.return_value = mock_results
            MockClient.return_value = mock_gmaps

            from geolocation_agent.tools.maps_tools import geocode

            result = geocode.invoke({"address": "Sydney, Australia"})
            data = json.loads(result)
            assert abs(data["latitude"] - (-33.8688)) < 0.001
            assert abs(data["longitude"] - 151.2093) < 0.001
            assert "Sydney" in data["formatted_address"]

    @patch("geolocation_agent.tools.maps_tools.get_settings")
    def test_handles_no_results(self, mock_settings):
        mock_settings.return_value.google_maps_api_key = "test-key"

        with patch("googlemaps.Client") as MockClient:
            mock_gmaps = MagicMock()
            mock_gmaps.geocode.return_value = []
            MockClient.return_value = mock_gmaps

            from geolocation_agent.tools.maps_tools import geocode

            result = geocode.invoke({"address": "xyznonexistent123"})
            data = json.loads(result)
            assert "error" in data


class TestReverseGeocode:
    @patch("geolocation_agent.tools.maps_tools.get_settings")
    def test_returns_address(self, mock_settings):
        mock_settings.return_value.google_maps_api_key = "test-key"

        mock_results = [{
            "formatted_address": "1 Macquarie St, Sydney NSW 2000, Australia",
            "types": ["street_address"],
            "place_id": "test_place_id",
        }]

        with patch("googlemaps.Client") as MockClient:
            mock_gmaps = MagicMock()
            mock_gmaps.reverse_geocode.return_value = mock_results
            MockClient.return_value = mock_gmaps

            from geolocation_agent.tools.maps_tools import reverse_geocode

            result = reverse_geocode.invoke({"lat": -33.8688, "lng": 151.2093})
            data = json.loads(result)
            assert len(data) == 1
            assert "Sydney" in data[0]["formatted_address"]


class TestGetSatelliteImage:
    @patch("geolocation_agent.tools.maps_tools.get_settings")
    @patch("geolocation_agent.tools.maps_tools.httpx")
    def test_saves_image_file(self, mock_httpx, mock_settings, tmp_path):
        mock_settings.return_value.google_maps_api_key = "test-key"
        mock_settings.return_value.tmp_dir = str(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        from geolocation_agent.tools.maps_tools import get_satellite_image

        result = get_satellite_image.invoke({
            "lat": -33.8688,
            "lng": 151.2093,
            "zoom": 18,
            "size": "600x400",
        })
        assert result.endswith("_satellite.jpg")


class TestGetStreetView:
    @patch("geolocation_agent.tools.maps_tools.get_settings")
    @patch("geolocation_agent.tools.maps_tools.httpx")
    def test_returns_error_when_unavailable(self, mock_httpx, mock_settings, tmp_path):
        mock_settings.return_value.google_maps_api_key = "test-key"
        mock_settings.return_value.tmp_dir = str(tmp_path)

        mock_meta_response = MagicMock()
        mock_meta_response.json.return_value = {"status": "ZERO_RESULTS"}
        mock_httpx.get.return_value = mock_meta_response

        from geolocation_agent.tools.maps_tools import get_street_view

        result = get_street_view.invoke({
            "lat": 0.0,
            "lng": 0.0,
        })
        data = json.loads(result)
        assert "error" in data
