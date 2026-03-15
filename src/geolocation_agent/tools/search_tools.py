"""Search tools: web search via Tavily, reverse image search via SerpAPI Google Lens."""

from __future__ import annotations

import base64
import json
import os
import uuid

import httpx
from langchain_core.tools import tool
from serpapi import GoogleSearch
from tavily import TavilyClient

from geolocation_agent.config import get_settings


@tool
def web_search(query: str, num_results: int = 10) -> str:
    """Search the web using Tavily for information relevant to geolocation.

    Args:
        query: The search query. Combine multiple clue dimensions for best results
               (e.g. "NSW South Coast winery with picnic lawn").
        num_results: Maximum number of results to return.

    Returns:
        JSON string with search results including title, URL, and content snippet.
    """
    settings = get_settings()
    client = TavilyClient(api_key=settings.tavily_api_key)
    response = client.search(query=query, max_results=num_results, search_depth="advanced")

    results = []
    for r in response.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        })

    return json.dumps(results, indent=2)


@tool
def reverse_image_search(image_path: str) -> str:
    """Run reverse image search using SerpAPI Google Lens on the full image.

    Uploads the image temporarily and searches for visual matches.

    Args:
        image_path: Path to the image file to search.

    Returns:
        JSON string with visual match results including titles, links, and sources.
    """
    image_url = _upload_image_for_search(image_path)
    return _run_google_lens(image_url)


@tool
def reverse_image_search_region(
    image_path: str, x: int, y: int, width: int, height: int
) -> str:
    """Crop a region of the image and run reverse image search on just that region.

    This is often more effective than searching the full image -- a cropped building
    facade, sign, or distinctive feature yields better matches.

    Args:
        image_path: Path to the source image.
        x: Left edge of crop box in pixels.
        y: Top edge of crop box in pixels.
        width: Width of crop box in pixels.
        height: Height of crop box in pixels.

    Returns:
        JSON string with visual match results.
    """
    from PIL import Image

    img = Image.open(image_path)
    img_w, img_h = img.size
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    right = min(x + width, img_w)
    bottom = min(y + height, img_h)

    cropped = img.crop((x, y, right, bottom))

    settings = get_settings()
    os.makedirs(settings.tmp_dir, exist_ok=True)
    crop_path = os.path.join(settings.tmp_dir, f"{uuid.uuid4().hex[:12]}_crop_search.jpg")
    cropped.convert("RGB").save(crop_path, "JPEG", quality=95)

    image_url = _upload_image_for_search(crop_path)
    return _run_google_lens(image_url)


def _upload_image_for_search(image_path: str) -> str:
    """Upload an image to a public host so SerpAPI can fetch it.

    Tries imgbb first (requires IMGBB_API_KEY env var). Falls back to a
    base64 data URI, which may not work with all search engines.
    """
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    imgbb_key = os.environ.get("IMGBB_API_KEY", "")
    if imgbb_key:
        try:
            response = httpx.post(
                "https://api.imgbb.com/1/upload",
                data={"key": imgbb_key, "image": image_data},
                timeout=30.0,
            )
            if response.status_code == 200:
                data = response.json()
                url = data["data"]["url"]
                return url
        except (httpx.HTTPError, KeyError):
            pass

    return f"data:image/jpeg;base64,{image_data}"


def _run_google_lens(image_url: str) -> str:
    """Run Google Lens search via SerpAPI.

    Returns a JSON string with results, or an error payload if the API
    call fails (e.g. bad URL, rate limit, empty response).
    """
    settings = get_settings()
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": settings.serpapi_api_key,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as exc:
        return json.dumps({
            "error": f"Google Lens search failed: {exc}",
            "visual_matches": [],
            "knowledge_graph": [],
        }, indent=2)

    if results.get("error"):
        return json.dumps({
            "error": results["error"],
            "visual_matches": [],
            "knowledge_graph": [],
        }, indent=2)

    visual_matches = []
    for match in results.get("visual_matches", [])[:15]:
        visual_matches.append({
            "title": match.get("title", ""),
            "link": match.get("link", ""),
            "source": match.get("source", ""),
            "thumbnail": match.get("thumbnail", ""),
        })

    knowledge_graph = results.get("knowledge_graph", [])
    if isinstance(knowledge_graph, list):
        kg_items = [
            {"title": kg.get("title", ""), "subtitle": kg.get("subtitle", "")}
            for kg in knowledge_graph[:5]
        ]
    else:
        kg_items = []

    related_content = []
    for item in results.get("related_content", []):
        entry = {"query": item.get("query", "")}
        if item.get("link"):
            entry["link"] = item["link"]
        related_content.append(entry)

    output = {
        "visual_matches": visual_matches,
        "knowledge_graph": kg_items,
    }
    if related_content:
        output["related_content"] = related_content

    return json.dumps(output, indent=2)
