# Geolocation Agent

**Where was this photo taken?** Drop in an image and let the agent work: it extracts clues, narrows regions, searches the web, checks maps and Street View, and iterates until it lands on a location—or admits it can't.

Inspired by Rainbolt-style geoguessing and the idea of automating OSINT. Vision LLM + search + maps, working like a detective.

## Setup

```bash
# Install dependencies
uv sync --all-extras

# Copy and fill in API keys
cp .env.example .env
```

## Usage

```bash
uv run python -m geolocation_agent <image_path>
```

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/
```
