"""Live API integration tests -- hits real services, prints results for review.

Run with:
    uv run python tests/test_live_apis.py          (standalone)
    uv run pytest tests/test_live_apis.py -m live   (via pytest)
"""

from __future__ import annotations

import json
import os
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

SEPARATOR = "=" * 70

pytestmark = pytest.mark.live


def test_tavily_web_search():
    print(f"\n{SEPARATOR}")
    print("TEST 1: Tavily Web Search")
    print(SEPARATOR)

    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(
        query="Coolangatta Estate winery Shoalhaven NSW",
        max_results=5,
        search_depth="advanced",
    )

    results = response.get("results", [])
    print(f"Got {len(results)} results\n")
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r.get('title', '?')}")
        print(f"      URL: {r.get('url', '?')}")
        print(f"      Score: {r.get('score', '?')}")
        snippet = r.get("content", "")[:150]
        print(f"      Snippet: {snippet}...")
        print()

    return len(results) > 0


def test_serpapi_google_lens():
    print(f"\n{SEPARATOR}")
    print("TEST 2: SerpAPI Google Lens (reverse image search)")
    print(SEPARATOR)

    from serpapi import GoogleSearch

    params = {
        "engine": "google_lens",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Sydney_Opera_House_from_the_air.jpg/1280px-Sydney_Opera_House_from_the_air.jpg",
        "api_key": os.environ["SERPAPI_API_KEY"],
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    visual_matches = results.get("visual_matches", [])
    knowledge_graph = results.get("knowledge_graph", [])

    print(f"Visual matches: {len(visual_matches)}")
    print(f"Knowledge graph entries: {len(knowledge_graph) if isinstance(knowledge_graph, list) else 'dict'}")

    if visual_matches:
        print("\nTop 5 visual matches:")
        for i, m in enumerate(visual_matches[:5]):
            print(f"  [{i+1}] {m.get('title', '?')}")
            print(f"      Link: {m.get('link', '?')}")
            print(f"      Source: {m.get('source', '?')}")
            print()

    if isinstance(knowledge_graph, list) and knowledge_graph:
        print("Knowledge graph:")
        for kg in knowledge_graph[:3]:
            print(f"  - {kg.get('title', '?')}: {kg.get('subtitle', '?')}")

    return len(visual_matches) > 0


def test_google_maps_geocode():
    print(f"\n{SEPARATOR}")
    print("TEST 3: Google Maps Geocoding")
    print(SEPARATOR)

    import googlemaps

    gmaps = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API_KEY"])

    print("Geocode: 'Sydney Opera House, Australia'")
    results = gmaps.geocode("Sydney Opera House, Australia")

    if results:
        top = results[0]
        loc = top["geometry"]["location"]
        print(f"  Address: {top.get('formatted_address', '?')}")
        print(f"  Lat: {loc['lat']}")
        print(f"  Lng: {loc['lng']}")
        print(f"  Place ID: {top.get('place_id', '?')}")
        print(f"  Types: {top.get('types', [])}")
    else:
        print("  No results!")

    print(f"\nReverse geocode: (-33.8568, 151.2153)")
    rev_results = gmaps.reverse_geocode((-33.8568, 151.2153))

    if rev_results:
        for i, r in enumerate(rev_results[:3]):
            print(f"  [{i+1}] {r.get('formatted_address', '?')}")
            print(f"       Types: {r.get('types', [])}")
    else:
        print("  No results!")

    return len(results) > 0


def test_google_maps_places():
    print(f"\n{SEPARATOR}")
    print("TEST 4: Google Maps Places Text Search")
    print(SEPARATOR)

    import googlemaps

    gmaps = googlemaps.Client(key=os.environ["GOOGLE_MAPS_API_KEY"])

    print("Text search: 'wineries near Berry NSW Australia'")
    results = gmaps.places(query="wineries near Berry NSW Australia")

    places = results.get("results", [])
    print(f"Got {len(places)} places\n")

    for i, p in enumerate(places[:5]):
        loc = p.get("geometry", {}).get("location", {})
        print(f"  [{i+1}] {p.get('name', '?')}")
        print(f"       Address: {p.get('formatted_address', '?')}")
        print(f"       Location: ({loc.get('lat', '?')}, {loc.get('lng', '?')})")
        print(f"       Rating: {p.get('rating', '?')} ({p.get('user_ratings_total', '?')} reviews)")
        print(f"       Types: {p.get('types', [])}")
        print()

    return len(places) > 0


def test_google_maps_street_view_metadata():
    print(f"\n{SEPARATOR}")
    print("TEST 5: Google Maps Street View Metadata Check")
    print(SEPARATOR)

    import httpx

    lat, lng = -33.8568, 151.2153
    print(f"Checking Street View availability at ({lat}, {lng}) -- Sydney Opera House")

    url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": f"{lat},{lng}",
        "key": os.environ["GOOGLE_MAPS_API_KEY"],
    }
    response = httpx.get(url, params=params, timeout=15.0)
    data = response.json()

    print(f"  Status: {data.get('status', '?')}")
    print(f"  Pano ID: {data.get('pano_id', 'N/A')}")
    if data.get("location"):
        print(f"  Actual location: ({data['location'].get('lat')}, {data['location'].get('lng')})")
    print(f"  Copyright: {data.get('copyright', 'N/A')}")

    return data.get("status") == "OK"


def main():
    tests = [
        ("Tavily Web Search", test_tavily_web_search),
        ("SerpAPI Google Lens", test_serpapi_google_lens),
        ("Google Maps Geocode", test_google_maps_geocode),
        ("Google Maps Places", test_google_maps_places),
        ("Street View Metadata", test_google_maps_street_view_metadata),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, "PASS" if passed else "FAIL (no results)"))
        except Exception as e:
            print(f"\n  ERROR: {type(e).__name__}: {e}")
            results.append((name, f"ERROR: {type(e).__name__}: {e}"))

    print(f"\n{SEPARATOR}")
    print("SUMMARY")
    print(SEPARATOR)
    for name, status in results:
        icon = "+" if status == "PASS" else "-"
        print(f"  {icon} {name}: {status}")
    print()


if __name__ == "__main__":
    main()
