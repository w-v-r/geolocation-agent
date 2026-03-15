"""Image inspection tools: crop, zoom, adjust, EXIF extraction, OCR."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import exifread
from langchain_core.tools import tool
from PIL import Image, ImageEnhance

from geolocation_agent.config import get_settings


def _ensure_tmp_dir() -> str:
    settings = get_settings()
    os.makedirs(settings.tmp_dir, exist_ok=True)
    return settings.tmp_dir


def _save_tmp_image(img: Image.Image, suffix: str = "") -> str:
    tmp_dir = _ensure_tmp_dir()
    filename = f"{uuid.uuid4().hex[:12]}{suffix}.jpg"
    path = os.path.join(tmp_dir, filename)
    img.convert("RGB").save(path, "JPEG", quality=95)
    return path


@tool
def crop_image(image_path: str, x: int, y: int, width: int, height: int) -> str:
    """Crop a rectangular region from the image.

    Args:
        image_path: Path to the source image.
        x: Left edge of crop box in pixels.
        y: Top edge of crop box in pixels.
        width: Width of crop box in pixels.
        height: Height of crop box in pixels.

    Returns:
        Path to the cropped image file.
    """
    img = Image.open(image_path)
    img_w, img_h = img.size
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    right = min(x + width, img_w)
    bottom = min(y + height, img_h)
    cropped = img.crop((x, y, right, bottom))
    return _save_tmp_image(cropped, "_crop")


@tool
def zoom_image(image_path: str, center_x: int, center_y: int, zoom_factor: float = 2.0) -> str:
    """Zoom into a point in the image by cropping around it and upscaling.

    Args:
        image_path: Path to the source image.
        center_x: X coordinate of the zoom center in pixels.
        center_y: Y coordinate of the zoom center in pixels.
        zoom_factor: How much to zoom in (2.0 = 2x zoom).

    Returns:
        Path to the zoomed image file.
    """
    img = Image.open(image_path)
    img_w, img_h = img.size

    crop_w = int(img_w / zoom_factor)
    crop_h = int(img_h / zoom_factor)

    x1 = max(0, center_x - crop_w // 2)
    y1 = max(0, center_y - crop_h // 2)
    x2 = min(img_w, x1 + crop_w)
    y2 = min(img_h, y1 + crop_h)

    if x2 - x1 < crop_w:
        x1 = max(0, x2 - crop_w)
    if y2 - y1 < crop_h:
        y1 = max(0, y2 - crop_h)

    cropped = img.crop((x1, y1, x2, y2))
    zoomed = cropped.resize((img_w, img_h), Image.LANCZOS)
    return _save_tmp_image(zoomed, "_zoom")


@tool
def adjust_image(
    image_path: str,
    brightness: float = 1.0,
    contrast: float = 1.0,
    sharpness: float = 1.0,
) -> str:
    """Adjust image brightness, contrast, and sharpness for better inspection.

    Args:
        image_path: Path to the source image.
        brightness: Brightness factor (1.0 = original, >1 brighter, <1 darker).
        contrast: Contrast factor (1.0 = original, >1 more contrast).
        sharpness: Sharpness factor (1.0 = original, >1 sharper).

    Returns:
        Path to the adjusted image file.
    """
    img = Image.open(image_path)

    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)

    return _save_tmp_image(img, "_adj")


@tool
def extract_exif(image_path: str) -> str:
    """Extract EXIF metadata from an image file.

    Returns a JSON string with all readable EXIF tags including GPS data,
    camera model, timestamps, and other metadata.

    Args:
        image_path: Path to the image file.

    Returns:
        JSON string of EXIF metadata. Returns '{}' if no EXIF data found.
    """
    with open(image_path, "rb") as f:
        tags = exifread.process_file(f, details=False)

    if not tags:
        return json.dumps({})

    result: dict[str, Any] = {}
    gps_data: dict[str, Any] = {}

    for key, value in tags.items():
        str_key = str(key)
        str_value = str(value)

        if str_key.startswith("GPS"):
            gps_data[str_key] = str_value
        else:
            result[str_key] = str_value

    if gps_data:
        result["GPS"] = gps_data
        lat = _parse_gps_coord(gps_data)
        if lat is not None:
            result["parsed_latitude"] = lat[0]
            result["parsed_longitude"] = lat[1]

    return json.dumps(result, indent=2)


def _parse_gps_coord(gps_data: dict[str, str]) -> tuple[float, float] | None:
    """Try to parse lat/lng from GPS EXIF tags."""
    try:
        lat_ref = gps_data.get("GPS GPSLatitudeRef", "N")
        lon_ref = gps_data.get("GPS GPSLongitudeRef", "E")
        lat_raw = gps_data.get("GPS GPSLatitude", "")
        lon_raw = gps_data.get("GPS GPSLongitude", "")

        if not lat_raw or not lon_raw:
            return None

        lat = _dms_to_decimal(lat_raw)
        lon = _dms_to_decimal(lon_raw)

        if lat_ref.strip().upper() == "S":
            lat = -lat
        if lon_ref.strip().upper() == "W":
            lon = -lon

        return (lat, lon)
    except (ValueError, IndexError, KeyError):
        return None


def _dms_to_decimal(dms_str: str) -> float:
    """Convert DMS string like '[34, 3, 1234/100]' to decimal degrees."""
    cleaned = dms_str.strip("[]() ")
    parts = [p.strip() for p in cleaned.split(",")]
    values: list[float] = []
    for part in parts:
        if "/" in part:
            num, den = part.split("/")
            values.append(float(num) / float(den))
        else:
            values.append(float(part))

    if len(values) < 3:
        return values[0] if values else 0.0

    return values[0] + values[1] / 60 + values[2] / 3600
