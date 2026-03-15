"""Places / POI lookup tools using Google Maps Places API."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from geolocation_agent.config import get_settings


@tool
def search_places_nearby(
    lat: float,
    lng: float,
    radius: int = 5000,
    place_type: str | None = None,
    keyword: str | None = None,
) -> str:
    """Search for places near a location using Google Maps Places API.

    Args:
        lat: Latitude of the search center.
        lng: Longitude of the search center.
        radius: Search radius in meters (max 50000).
        place_type: Google Places type filter (e.g. 'restaurant', 'lodging', 'tourist_attraction').
        keyword: Keyword to filter results (e.g. 'winery', 'lookout').

    Returns:
        JSON string with a list of nearby places including name, address, location, and rating.
    """
    settings = get_settings()

    import googlemaps

    gmaps = googlemaps.Client(key=settings.google_maps_api_key)

    kwargs: dict = {
        "location": (lat, lng),
        "radius": min(radius, 50000),
    }
    if place_type:
        kwargs["type"] = place_type
    if keyword:
        kwargs["keyword"] = keyword

    results = gmaps.places_nearby(**kwargs)

    places = []
    for place in results.get("results", [])[:20]:
        loc = place.get("geometry", {}).get("location", {})
        places.append({
            "name": place.get("name", ""),
            "place_id": place.get("place_id", ""),
            "address": place.get("vicinity", ""),
            "latitude": loc.get("lat"),
            "longitude": loc.get("lng"),
            "types": place.get("types", []),
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total"),
        })

    return json.dumps(places, indent=2)


@tool
def search_places_text(query: str) -> str:
    """Search for places using a text query via Google Maps Places API.

    This is useful for finding specific businesses or landmarks by name and description.

    Args:
        query: Natural language search query (e.g. 'wineries near Berry NSW',
               'lookout cafe with ocean view Sydney').

    Returns:
        JSON string with matching places including name, address, location, and rating.
    """
    settings = get_settings()

    import googlemaps

    gmaps = googlemaps.Client(key=settings.google_maps_api_key)
    results = gmaps.places(query=query)

    places = []
    for place in results.get("results", [])[:20]:
        loc = place.get("geometry", {}).get("location", {})
        places.append({
            "name": place.get("name", ""),
            "place_id": place.get("place_id", ""),
            "address": place.get("formatted_address", ""),
            "latitude": loc.get("lat"),
            "longitude": loc.get("lng"),
            "types": place.get("types", []),
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total"),
        })

    return json.dumps(places, indent=2)


@tool
def get_place_details(place_id: str) -> str:
    """Get detailed information about a specific place using its Google Place ID.

    Args:
        place_id: The Google Maps place_id obtained from a previous search.

    Returns:
        JSON string with detailed place info including name, address, phone,
        website, opening hours, reviews, and photos.
    """
    settings = get_settings()

    import googlemaps

    gmaps = googlemaps.Client(key=settings.google_maps_api_key)
    result = gmaps.place(place_id=place_id)

    place = result.get("result", {})
    loc = place.get("geometry", {}).get("location", {})

    photos = []
    for photo in place.get("photos", [])[:5]:
        photos.append({
            "photo_reference": photo.get("photo_reference", ""),
            "width": photo.get("width"),
            "height": photo.get("height"),
        })

    return json.dumps({
        "name": place.get("name", ""),
        "place_id": place.get("place_id", ""),
        "address": place.get("formatted_address", ""),
        "latitude": loc.get("lat"),
        "longitude": loc.get("lng"),
        "phone": place.get("formatted_phone_number", ""),
        "website": place.get("website", ""),
        "types": place.get("types", []),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("user_ratings_total"),
        "opening_hours": place.get("opening_hours", {}).get("weekday_text", []),
        "reviews": [
            {"text": r.get("text", ""), "rating": r.get("rating")}
            for r in place.get("reviews", [])[:3]
        ],
        "photos": photos,
    }, indent=2)
