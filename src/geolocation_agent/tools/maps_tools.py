"""Maps and geospatial tools: satellite imagery, Street View, geocoding."""

from __future__ import annotations

import json
import os
import uuid

import httpx
from langchain_core.tools import tool

from geolocation_agent.config import get_settings


@tool
def get_satellite_image(
    lat: float,
    lng: float,
    zoom: int = 18,
    size: str = "600x400",
) -> str:
    """Fetch a satellite image of a location using Google Maps Static API.

    Args:
        lat: Latitude of the center point.
        lng: Longitude of the center point.
        zoom: Zoom level (1=world, 20=buildings). Default 18.
        size: Image dimensions as 'WIDTHxHEIGHT'. Default '600x400'.

    Returns:
        Path to the saved satellite image file.
    """
    settings = get_settings()
    os.makedirs(settings.tmp_dir, exist_ok=True)

    url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lng}",
        "zoom": zoom,
        "size": size,
        "maptype": "satellite",
        "key": settings.google_maps_api_key,
    }

    response = httpx.get(url, params=params, timeout=30.0)
    response.raise_for_status()

    filename = f"{uuid.uuid4().hex[:12]}_satellite.jpg"
    path = os.path.join(settings.tmp_dir, filename)
    with open(path, "wb") as f:
        f.write(response.content)

    return path


@tool
def get_street_view(
    lat: float,
    lng: float,
    heading: float = 0,
    pitch: float = 0,
    fov: int = 90,
    size: str = "600x400",
) -> str:
    """Fetch a Street View image from a location using Google Street View Static API.

    Args:
        lat: Latitude.
        lng: Longitude.
        heading: Camera heading in degrees (0=North, 90=East, 180=South, 270=West).
        pitch: Camera pitch (-90=down, 0=horizontal, 90=up).
        fov: Field of view in degrees (10-120). Smaller = more zoom.
        size: Image dimensions as 'WIDTHxHEIGHT'.

    Returns:
        Path to the saved Street View image file, or error message if unavailable.
    """
    settings = get_settings()
    os.makedirs(settings.tmp_dir, exist_ok=True)

    metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    meta_params = {
        "location": f"{lat},{lng}",
        "key": settings.google_maps_api_key,
    }

    meta_response = httpx.get(metadata_url, params=meta_params, timeout=15.0)
    meta_data = meta_response.json()

    if meta_data.get("status") != "OK":
        return json.dumps({
            "error": "No Street View available at this location",
            "status": meta_data.get("status"),
        })

    url = "https://maps.googleapis.com/maps/api/streetview"
    params = {
        "location": f"{lat},{lng}",
        "heading": heading,
        "pitch": pitch,
        "fov": fov,
        "size": size,
        "key": settings.google_maps_api_key,
    }

    response = httpx.get(url, params=params, timeout=30.0)
    response.raise_for_status()

    filename = f"{uuid.uuid4().hex[:12]}_streetview.jpg"
    path = os.path.join(settings.tmp_dir, filename)
    with open(path, "wb") as f:
        f.write(response.content)

    return path


@tool
def geocode(address: str) -> str:
    """Convert an address or place name to latitude/longitude coordinates.

    Args:
        address: The address or place name to geocode.

    Returns:
        JSON string with lat, lng, formatted_address, and place_id.
    """
    settings = get_settings()

    import googlemaps

    gmaps = googlemaps.Client(key=settings.google_maps_api_key)
    results = gmaps.geocode(address)

    if not results:
        return json.dumps({"error": f"No results found for: {address}"})

    top = results[0]
    location = top["geometry"]["location"]

    return json.dumps({
        "latitude": location["lat"],
        "longitude": location["lng"],
        "formatted_address": top.get("formatted_address", ""),
        "place_id": top.get("place_id", ""),
        "types": top.get("types", []),
    }, indent=2)


@tool
def reverse_geocode(lat: float, lng: float) -> str:
    """Convert latitude/longitude coordinates to an address.

    Args:
        lat: Latitude.
        lng: Longitude.

    Returns:
        JSON string with formatted address and location details.
    """
    settings = get_settings()

    import googlemaps

    gmaps = googlemaps.Client(key=settings.google_maps_api_key)
    results = gmaps.reverse_geocode((lat, lng))

    if not results:
        return json.dumps({"error": f"No address found for: {lat}, {lng}"})

    addresses = []
    for r in results[:3]:
        addresses.append({
            "formatted_address": r.get("formatted_address", ""),
            "types": r.get("types", []),
            "place_id": r.get("place_id", ""),
        })

    return json.dumps(addresses, indent=2)
