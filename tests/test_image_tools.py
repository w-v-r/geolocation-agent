"""Tests for image inspection tools."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from PIL import Image

from geolocation_agent.tools.image_tools import (
    _dms_to_decimal,
    adjust_image,
    crop_image,
    extract_exif,
    zoom_image,
)


@pytest.fixture(autouse=True)
def _use_tmp_dir(tmp_dir):
    with patch("geolocation_agent.tools.image_tools.get_settings") as mock_settings:
        settings = mock_settings.return_value
        settings.tmp_dir = tmp_dir
        yield


class TestCropImage:
    def test_basic_crop(self, test_image_path):
        result = crop_image.invoke({
            "image_path": test_image_path,
            "x": 100,
            "y": 100,
            "width": 200,
            "height": 150,
        })
        assert os.path.exists(result)
        img = Image.open(result)
        assert img.size == (200, 150)

    def test_crop_clamped_to_image_bounds(self, test_image_path):
        result = crop_image.invoke({
            "image_path": test_image_path,
            "x": 700,
            "y": 500,
            "width": 500,
            "height": 500,
        })
        assert os.path.exists(result)
        img = Image.open(result)
        assert img.size[0] <= 800
        assert img.size[1] <= 600

    def test_crop_at_origin(self, test_image_path):
        result = crop_image.invoke({
            "image_path": test_image_path,
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 100,
        })
        img = Image.open(result)
        assert img.size == (100, 100)


class TestZoomImage:
    def test_basic_zoom(self, test_image_path):
        result = zoom_image.invoke({
            "image_path": test_image_path,
            "center_x": 400,
            "center_y": 300,
            "zoom_factor": 2.0,
        })
        assert os.path.exists(result)
        img = Image.open(result)
        assert img.size == (800, 600)

    def test_zoom_corner(self, test_image_path):
        result = zoom_image.invoke({
            "image_path": test_image_path,
            "center_x": 0,
            "center_y": 0,
            "zoom_factor": 3.0,
        })
        assert os.path.exists(result)
        img = Image.open(result)
        assert img.size == (800, 600)


class TestAdjustImage:
    def test_brighten(self, test_image_path):
        result = adjust_image.invoke({
            "image_path": test_image_path,
            "brightness": 1.5,
            "contrast": 1.0,
            "sharpness": 1.0,
        })
        assert os.path.exists(result)

    def test_high_contrast_and_sharp(self, test_image_path):
        result = adjust_image.invoke({
            "image_path": test_image_path,
            "brightness": 1.0,
            "contrast": 2.0,
            "sharpness": 2.0,
        })
        assert os.path.exists(result)

    def test_no_change(self, test_image_path):
        result = adjust_image.invoke({
            "image_path": test_image_path,
            "brightness": 1.0,
            "contrast": 1.0,
            "sharpness": 1.0,
        })
        assert os.path.exists(result)


class TestExtractExif:
    def test_no_exif_data(self, test_image_path):
        result = extract_exif.invoke({"image_path": test_image_path})
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_returns_valid_json(self, test_image_path):
        result = extract_exif.invoke({"image_path": test_image_path})
        parsed = json.loads(result)
        assert parsed is not None


class TestDmsToDecimal:
    def test_simple_integer_parts(self):
        assert abs(_dms_to_decimal("[34, 3, 36]") - 34.06) < 0.01

    def test_fractional_seconds(self):
        result = _dms_to_decimal("[151, 12, 1234/100]")
        assert abs(result - 151.20343) < 0.001

    def test_single_value(self):
        assert _dms_to_decimal("45") == 45.0
