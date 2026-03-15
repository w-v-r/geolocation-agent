"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def test_image_path() -> str:
    path = os.path.join(os.path.dirname(__file__), "fixtures", "test_image.jpg")
    assert os.path.exists(path), f"Test fixture image not found at {path}"
    return path


@pytest.fixture
def tmp_dir(tmp_path) -> str:
    return str(tmp_path)
