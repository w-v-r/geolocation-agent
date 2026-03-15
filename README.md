# Geolocation Agent

A geolocation agent that determines where a photo was taken through iterative hypothesis testing.

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
