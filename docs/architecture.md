# Architecture

## Overview

The geolocation agent is a LangGraph-based system that determines where a photograph was taken through iterative hypothesis testing. It combines vision LLM analysis with external tools (web search, reverse image search, maps, places) to progressively narrow down a location.

## Core Design

### State Machine

The agent operates as a state machine with the following nodes:

```
Start → extract_metadata → analyze_image → generate_hypotheses → investigate
                                                ↑                    ↓
                                                └── (not confident) ←┘
                                                         ↓ (confident)
                                                    produce_report → End
```

### Agent State

All data flows through a single `AgentState` that accumulates across iterations:

- `image_path` / `side_info`: Input data
- `clues`: Extracted visual observations
- `hypotheses`: Location hypotheses at various specificity levels
- `candidates`: Specific candidate locations with coordinates
- `evidence_log`: Evidence for/against each hypothesis and candidate
- `eliminated`: Ruled-out candidates with reasons
- `confidence`: Current best confidence score
- `iteration` / `max_iterations`: Loop control
- `messages`: LLM conversation history
- `final_answer`: Structured result when investigation concludes

### Reducer Pattern

Lists in the state use a `merge_lists` reducer that merges by ID. This means:
- Adding a new clue with a unique ID appends it
- Adding a clue with an existing ID updates it
- State never grows unboundedly with duplicates

## Node Descriptions

### extract_metadata
Runs EXIF extraction on the input image. If GPS coordinates are found, they are recorded as high-confidence clues. Camera model and timestamp are also captured. This is the only deterministic (no LLM) node.

### analyze_image
Sends the image to the vision LLM with the analysis prompt. The LLM can use image tools (crop, zoom, adjust) to inspect details. It records observations as clues via the evidence tracker.

### generate_hypotheses
The LLM reviews all accumulated clues and evidence to propose or refine hypotheses. Hypotheses are structured with level (country/region/city/venue), confidence, and supporting clue IDs. Sub-hypotheses are encouraged.

### investigate
The core investigation loop. The LLM has access to ALL tools and decides which to use based on current hypotheses and evidence gaps. This includes:
- Web search (Tavily)
- Reverse image search (SerpAPI Google Lens)
- Places lookup (Google Maps Places)
- Satellite imagery (Google Maps Static API)
- Street View (Google Street View)
- Geocoding / reverse geocoding
- Evidence tracking

### should_continue (conditional edge)
Checks whether to loop back or proceed to report:
- If confidence >= threshold (default 0.8): report
- If iterations >= max (default 10): report
- Otherwise: loop back to generate_hypotheses

### produce_report
Generates the final structured answer with best candidate, alternatives, confidence levels, key evidence, and a reasoning narrative.

## LLM Provider Architecture

The system supports three LLM providers via a factory pattern:
- **OpenAI** (default): GPT-4o with vision
- **Anthropic**: Claude Sonnet with vision
- **Google**: Gemini 2.0 Flash with vision

Provider selection is controlled by the `LLM_PROVIDER` environment variable. All providers must support multimodal (vision) input since the agent needs to analyze photographs.

## Tool Architecture

Tools are implemented as LangChain `@tool` decorated functions. They are grouped by capability:

1. **Image Tools**: Local image processing (Pillow-based)
2. **Search Tools**: External web/image search APIs
3. **Maps Tools**: Google Maps Platform APIs
4. **Places Tools**: Google Maps Places API
5. **Evidence Tracker**: Pure logic, no external API calls

Tool sets are composed for each node:
- `ANALYSIS_TOOLS`: Image tools + add_clue (for the analyze node)
- `ALL_TOOLS`: Everything (for the investigate node)

### Image Path Injection

Image tools (`crop_image`, `zoom_image`, `adjust_image`, `extract_exif`, `reverse_image_search`, `reverse_image_search_region`) require a local file path. Because the LLM does not reliably produce the correct path, the `_inject_image_path` helper in `nodes.py` intercepts tool calls and overrides the `image_path` argument with the real path from agent state. The path is resolved to an absolute path at the start of the investigation in `run_investigation()`.

## Progress Logging

Each node prints timestamped progress messages to stderr so the user can monitor the investigation in real time. Messages include phase transitions, tool calls with their arguments, extracted clues, hypotheses, candidates, evidence, and confidence updates.
