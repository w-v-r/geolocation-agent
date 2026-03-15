"""Geolocation agent tools."""

from geolocation_agent.tools.evidence_tracker import (
    add_candidate,
    add_clue,
    add_evidence,
    add_hypothesis,
    eliminate_candidate,
    get_investigation_summary,
    update_confidence,
)
from geolocation_agent.tools.image_tools import (
    adjust_image,
    crop_image,
    extract_exif,
    zoom_image,
)
from geolocation_agent.tools.maps_tools import (
    geocode,
    get_satellite_image,
    get_street_view,
    reverse_geocode,
)
from geolocation_agent.tools.places_tools import (
    get_place_details,
    search_places_nearby,
    search_places_text,
)
from geolocation_agent.tools.search_tools import (
    reverse_image_search,
    reverse_image_search_region,
    web_search,
)

ALL_TOOLS = [
    crop_image,
    zoom_image,
    adjust_image,
    extract_exif,
    web_search,
    reverse_image_search,
    reverse_image_search_region,
    get_satellite_image,
    get_street_view,
    geocode,
    reverse_geocode,
    search_places_nearby,
    search_places_text,
    get_place_details,
    add_clue,
    add_hypothesis,
    add_candidate,
    add_evidence,
    eliminate_candidate,
    update_confidence,
    get_investigation_summary,
]

INVESTIGATION_TOOLS = ALL_TOOLS

ANALYSIS_TOOLS = [
    crop_image,
    zoom_image,
    adjust_image,
    extract_exif,
    add_clue,
]

__all__ = [
    "ALL_TOOLS",
    "INVESTIGATION_TOOLS",
    "ANALYSIS_TOOLS",
    "crop_image",
    "zoom_image",
    "adjust_image",
    "extract_exif",
    "web_search",
    "reverse_image_search",
    "reverse_image_search_region",
    "get_satellite_image",
    "get_street_view",
    "geocode",
    "reverse_geocode",
    "search_places_nearby",
    "search_places_text",
    "get_place_details",
    "add_clue",
    "add_hypothesis",
    "add_candidate",
    "add_evidence",
    "eliminate_candidate",
    "update_confidence",
    "get_investigation_summary",
]
